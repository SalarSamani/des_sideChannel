#!/usr/bin/env python3
import os
import sys
import time
import numpy as np
import chipwhisperer as cw

from sbox_out import sbox_out


# --------- config ---------
TRACES_DIR = "traces"

# capture settings: adjust if needed
SAMPLES = 5000        # number of ADC samples per trace
DECIMATE = 1
OFFSET = 0        # start at original sample index
# --------------------------


scope = None
target = None


# ========== ChipWhisperer setup ==========

def init_scope():
    global scope, target
    try:
        scope = cw.scope(sn="442031204c5032433130333234313031")
        target = cw.target(scope)
        scope.default_setup()
        print("[INFO] Found ChipWhisperer ✅")
    except Exception as e:
        print("[ERROR] Could not connect to ChipWhisperer:", e)
        raise


def reset_target():
    global scope
    scope.io.nrst = "low"
    time.sleep(0.05)
    scope.io.nrst = "high_z"
    time.sleep(0.05)


def capture_one_trace(pt_bytes, idx):
    """
    Capture ONE trace for 8-byte plaintext pt_bytes with:
      - samples = SAMPLES
      - decimate = DECIMATE
      - offset   = OFFSET
    Returns the trace as a 1D NumPy array or None on timeout.
    """
    global scope, target

    scope.adc.samples = SAMPLES
    scope.adc.decimate = DECIMATE
    scope.adc.offset = OFFSET
    scope.adc.presamples = 0
    scope.adc.timeout = 2

    print(f"\n[INFO] Capturing trace {idx}")
    print("  pt      =", pt_bytes.hex())
    print("  samples =", scope.adc.samples)
    print("  decim   =", scope.adc.decimate)
    print("  offset  =", scope.adc.offset)

    scope.arm()
    target.simpleserial_write('d', pt_bytes)
    # ct = target.simpleserial_read('r', 8)
    # print("  ct      =", ct.hex())

    if scope.capture():
        print("[ERROR] Capture timed out")
        return None

    trace = np.array(scope.get_last_trace(), dtype=float)
    print("  trace length =", len(trace))

    # optionally save per-trace if you like
    os.makedirs(TRACES_DIR, exist_ok=True)
    np.save(os.path.join(TRACES_DIR, f"trace_{idx:04d}.npy"), trace)

    return trace


# ========== helper functions ==========

def generate_random_plaintexts(n):
    """
    Generate n random 64-bit plaintexts using os.urandom.
    Returns a list of integers.
    """
    pts = []
    for _ in range(n):
        val = int.from_bytes(os.urandom(8), "big")  # 64-bit
        pts.append(val)
    print(f"[INFO] Generated {n} random plaintexts in memory")
    return pts


def plaintext_int_to_bytes(pt_int):
    """Convert 64-bit integer plaintext to 8-byte big-endian for serial send."""
    return pt_int.to_bytes(8, "big")


# ========== DPA using pre-captured traces ==========

def run_dpa_all_sboxes(traces, plaintexts_int):
    """
    Capture phase is already done.
    Now DPA phase using global traces:

    for each sbox (1,8)
        for each key (0,63)
            using sbox_out divide the plaintext indices into zero_list and one_list
                zero_indices = [i where LSB(sbox_out(sbox, PT[i], key)) == 0]
                one_indices  = [i where LSB(sbox_out(sbox, PT[i], key)) == 1]
            zero_traces = traces[zero_indices]
            one_traces  = traces[one_indices]

            avg_zero = mean(zero_traces, axis=0)
            avg_one  = mean(one_traces, axis=0)

            diff_trace = abs(avg_one - avg_zero)
            peak_value = max(diff_trace)
            peak_index = argmax(diff_trace)
            store (key, peak_value, peak_index) for this sbox

        at the end for this sbox:
            sort all keys by peak_value
            take top 5
    """
    num_traces, trace_len = traces.shape
    print(f"[INFO] DPA phase on {num_traces} traces, trace_len={trace_len}")

    all_results = {}   # sbox_num -> list of (key, peak, idx)

    for sbox_num in range(1, 9):
        print(f"\n[INFO] === DPA for S-box {sbox_num} ===")

        sbox_results = []

        for guess_key in range(64):
            zero_indices = []
            one_indices = []

            # build zero/one lists by index
            for i, pt_int in enumerate(plaintexts_int):
                val = sbox_out(sbox_num, pt_int, guess_key)  # 0..15
                bit = val & 1   # LSB

                if bit == 0:
                    zero_indices.append(i)
                else:
                    one_indices.append(i)

            n_zero = len(zero_indices)
            n_one = len(one_indices)
            print(f"  S{sbox_num} key={guess_key:02d}: "
                  f"{n_zero} zero, {n_one} one")

            # skip if one of the groups is empty
            if n_zero == 0 or n_one == 0:
                continue

            zero_traces = traces[zero_indices]
            one_traces  = traces[one_indices]

            avg_zero = np.mean(zero_traces, axis=0)
            avg_one  = np.mean(one_traces, axis=0)

            diff = np.abs(avg_one - avg_zero)

            max_peak = float(np.max(diff))
            peak_index = int(np.argmax(diff))

            print(f"    -> max_peak={max_peak:.6f} at sample {peak_index}")

            sbox_results.append((guess_key, max_peak, peak_index))

        # sort by peak descending for this S-box
        sbox_results.sort(key=lambda x: x[1], reverse=True)
        all_results[sbox_num] = sbox_results

    return all_results


# ========== main: capture phase + DPA phase ==========

def main():
    # ----- parse command line: ./dpa.py <n_traces> -----
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <n_traces>")
        sys.exit(1)

    try:
        n_traces = int(sys.argv[1])
        if n_traces <= 0:
            raise ValueError
    except ValueError:
        print("[ERROR] <n_traces> must be a positive integer")
        sys.exit(1)

    print(f"[INFO] Requested {n_traces} traces")

    # ----- generate plaintexts in memory -----
    plaintexts_int_all = generate_random_plaintexts(n_traces)

    # ----- Capture phase -----
    init_scope()
    reset_target()

    traces_list = []
    used_plaintexts_int = []

    for idx, pt_int in enumerate(plaintexts_int_all):
        pt_bytes = plaintext_int_to_bytes(pt_int)
        trace = capture_one_trace(pt_bytes, idx)

        if trace is None:
            print(f"[WARN] Skipping plaintext index {idx} due to capture error.")
            continue

        traces_list.append(trace)
        used_plaintexts_int.append(pt_int)

    if len(traces_list) == 0:
        print("[ERROR] No traces captured, aborting DPA.")
        scope.dis()
        target.dis()
        return

    traces = np.vstack(traces_list)
    plaintexts_int = used_plaintexts_int

    # (optional) save combined arrays
    os.makedirs(TRACES_DIR, exist_ok=True)
    np.save(os.path.join(TRACES_DIR, "traces_all.npy"), traces)
    np.save(os.path.join(TRACES_DIR, "plaintexts_all.npy"),
            np.array(plaintexts_int, dtype=np.uint64))

    print(f"\n[INFO] Capture done. Traces shape = {traces.shape}")
    print(f"[INFO] Starting DPA phase using pre-captured traces.")

    # ----- DPA phase -----
    all_results = run_dpa_all_sboxes(traces, plaintexts_int)

    # print top 5 per S-box
    print("\n=== DPA top 5 keys per S-box (reuse traces) ===")
    for sbox_num in range(1, 9):
        sbox_results = all_results.get(sbox_num, [])
        if not sbox_results:
            print(f"\nS-box {sbox_num}: no valid results")
            continue

        top5 = sbox_results[:5]
        print(f"\nS-box {sbox_num}:")
        for rank, (key, peak, idx) in enumerate(top5, start=1):
            original_sample = OFFSET + idx * DECIMATE
            print(f"  #{rank}: key= (0x{key:02X}), "
                  f"max_peak={peak:.6f}, "
                  f"sample={idx} (original ≈ {original_sample})")

    # cleanup
    scope.dis()
    target.dis()


if __name__ == "__main__":
    main()

