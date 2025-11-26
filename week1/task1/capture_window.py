import chipwhisperer as cw
import time
import numpy as np
import matplotlib.pyplot as plt
import sys

scope = None
target = None

# ---------- DEFAULTS IF NO ARGS ----------
DEFAULT_OFFSET = 0      # A
DEFAULT_SAMPLES = 2000  # S


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


def capture_window(offset, samples, plaintext):
    """Capture window starting at offset A with size S, decimate=1."""
    global scope, target

    # --- ADC setup ---
    scope.adc.samples = samples
    scope.adc.decimate = 1        # as requested
    scope.adc.offset = offset
    scope.adc.presamples = 0
    scope.adc.timeout = 2

    print("\n[INFO] Capture settings")
    print("  offset  =", scope.adc.offset)
    print("  samples =", scope.adc.samples)
    print("  decimate=", scope.adc.decimate)

    scope.arm()
    target.simpleserial_write('d', plaintext)
    ciphertext = target.simpleserial_read('r', 8)
    print("[INFO] Ciphertext =", ciphertext.hex())

    if scope.capture():
        print("[ERROR] Capture timed out")
        return

    trace = np.array(scope.get_last_trace(), dtype=float)
    print("[INFO] Got trace of length", len(trace))

    end = offset + samples
    base_name = f"trace_{offset}_{end}"

    # Save raw data
    np.save(base_name + ".npy", trace)
    print(f"[INFO] Saved data to {base_name}.npy")

    # Save PNG
    plt.figure(figsize=(10, 3))
    x = np.arange(len(trace))
    plt.plot(x, trace, linewidth=0.6)
    plt.title(f"Power trace – offset={offset}, samples={samples}, decimate=1")
    plt.xlabel("Sample index (this window)")
    plt.ylabel("Power (ADC units)")

    tick_step = max(1, len(trace) // 20)   # ~20 ticks
    plt.xticks(np.arange(0, len(trace) + 1, tick_step))
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(base_name + ".png", dpi=300)
    plt.close()
    print(f"[INFO] Saved plot to {base_name}.png")


def main():
    init()
    reset_target()

    # read A and S from command line if provided
    if len(sys.argv) >= 3:
        try:
            offset = int(sys.argv[1])
            samples = int(sys.argv[2])
        except ValueError:
            print("[ERROR] offset and samples must be integers.")
            return
    else:
        offset = DEFAULT_OFFSET
        samples = DEFAULT_SAMPLES
        print(f"[INFO] Using default OFFSET={offset}, SAMPLES={samples} "
              f"(you can override: python3 script.py <offset> <samples>)")

    pt = b"HWSEC_25"
    capture_window(offset, samples, pt)


if __name__ == "__main__":
    main()
