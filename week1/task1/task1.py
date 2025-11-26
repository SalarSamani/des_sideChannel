import chipwhisperer as cw
import time
import numpy as np
import matplotlib.pyplot as plt

scope = None
target = None

def init():
    global scope, target
    try:
        scope = cw.scope(sn="442031204c5032433130333234313031")
        target = cw.target(scope)
        scope.default_setup()
        print("[INFO] Found ChipWhisperer 😍")
    except Exception as e:
        print("[ERROR] Could not connect to ChipWhisperer:", e)
        exit(-1)

def reset_target():
    global scope
    scope.io.nrst = 'low'
    time.sleep(0.05)
    scope.io.nrst = 'high_z'
    time.sleep(0.05)

def capture_step(samples, decimate, offset, plaintext, step_idx):
    """Capture one trace at given offset and return the trace array."""
    global scope, target

    scope.adc.samples = samples
    scope.adc.decimate = decimate
    scope.adc.offset = offset
    scope.adc.presamples = 0
    scope.adc.timeout = 2

    print(f"\n[INFO] Capturing step {step_idx}")
    print("  samples  =", scope.adc.samples)
    print("  decimate =", scope.adc.decimate)
    print("  offset   =", scope.adc.offset)

    scope.arm()
    target.simpleserial_write('d', plaintext)
    ciphertext = target.simpleserial_read('r', 8)
    print("  Ciphertext =", ciphertext.hex())

    if scope.capture():
        print("[ERROR] Capture timed out")
        return None

    trace = np.array(scope.get_last_trace(), dtype=float)
    print("  Trace length =", len(trace))

    # save raw data
    np.save(f"trace_step{step_idx}.npy", trace)
    print(f"  Saved step {step_idx} raw data to trace_step{step_idx}.npy")

    # ---- per-step PNG ----
    plt.figure(figsize=(10, 3))
    x = np.arange(len(trace))
    plt.plot(x, trace, linewidth=0.6)
    plt.title(f"Power trace – step {step_idx} (samples={samples}, decimate={decimate})")
    plt.xlabel("Sample index (this step)")
    plt.ylabel("Power (ADC units)")

    # ticks every ~len/20 samples, and rotate labels 45 degrees
    step_tick = max(1, len(trace) // 20)   # about ~20 ticks max
    tick_positions = np.arange(0, len(trace) + 1, step_tick)
    plt.xticks(tick_positions, rotation=45)

    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"trace_step{step_idx}.png", dpi=300)
    plt.close()
    print(f"  Saved step {step_idx} plot to trace_step{step_idx}.png")
    return trace

def main():
    init()
    reset_target()

    pt = b"HWSEC_25"

    SAMPLES = 24400
    DECIMATE = 2
    N_STEPS = 8
    OFFSET_STEP = SAMPLES * DECIMATE  # real-time distance between step windows

    all_traces = []

    for i in range(N_STEPS):
        offset = i * OFFSET_STEP
        trace = capture_step(SAMPLES, DECIMATE, offset, pt, step_idx=i+1)
        if trace is None:
            print(f"[WARN] Step {i+1} failed, skipping in combined plot")
            continue
        all_traces.append(trace)

    if not all_traces:
        print("[ERROR] No traces captured, nothing to combine.")
        return

    # Concatenate all traces to make one long signal
    combined_trace = np.concatenate(all_traces)
    print("\n[INFO] Combined trace length =", len(combined_trace))

    np.save("trace_steps_combined.npy", combined_trace)
    print("[INFO] Saved combined raw data to trace_steps_combined.npy")

    # ---- combined PNG (all data, rotated labels) ----
    plt.figure(figsize=(14, 4))
    x = np.arange(len(combined_trace))
    plt.plot(x, combined_trace, linewidth=0.6)
    plt.title(f"Combined power trace over {len(all_traces)} steps "
              f"(samples={SAMPLES}, decimate={DECIMATE})")
    plt.xlabel("Sample index (across all steps)")
    plt.ylabel("Power (ADC units)")

    # choose tick spacing so labels don't overlap but still fairly dense
    max_ticks = 20  # ~max number of labels
    tick_interval = max(1, len(combined_trace) // max_ticks)
    tick_positions = np.arange(0, len(combined_trace) + 1, tick_interval)
    plt.xticks(tick_positions, rotation=45)

    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("trace_steps_combined.png", dpi=300)
    plt.close()
    print("[INFO] Saved combined plot to trace_steps_combined.png")

if __name__ == "__main__":
    main()
