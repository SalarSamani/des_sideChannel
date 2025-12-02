#!/usr/bin/env python3
import os
import sys
import time
import numpy as np
import chipwhisperer as cw

from sbox_out import sbox_out


# --------- config ---------
TRACES_DIR = "traces_cpa"

# capture settings for CPA
SAMPLES = 200        # number of ADC samples per trace
DECIMATE = 1
OFFSET = 3800        # start sample index
# --------------------------


scope = None
target = None


# ========== ChipWhisperer setup ==========

def init_scope():
    global scope, target
    try:
        # use your board serial number if needed, or remove sn=... for auto-detect
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

    # optionally save per-trace
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


def hamming_weight(x):
    """Hamming weight of an integer (number of '1' bits)."""
    return bin(x).count("1")


# ========== CPA helper: precompute hypothetical power (N x 64) for any S-box ==========

def precompute_hypothetical_hw_for_sbox(sbox_num, plaintexts_int):
    """
    For a given S-box (1..8):
    Build a matrix HW[guess_k][trace_index] = HW( sbox_out(sbox_num, PT[trace_index], guess_k) )

    This matches your structure:

    (P0, k0)   -> HW(...)
    (P1, k0)   -> HW(...)
    ...
    (P(N-1), k0)
    ...
    (P(N-1), k63)
    """
    num_traces = len(plaintexts_int)
    hw_table = np.array([hamming_weight(v) for v in range(16)], dtype=float)

    hyp_hw = np.zeros((64, num_traces), dtype=float)

    print(f"\n[INFO] Precomputing hypothetical HW for S-box {sbox_num}...")
    for guess_k in range(64):
        for i, pt_int in enumerate(plaintexts_int):
            sbox_val = sbox_out(sbox_num, pt_int, guess_k)  # 0..15
            hyp_hw[guess_k, i] = hw_table[sbox_val]
        print(f"  S{sbox_num} key={guess_k:02d} done")

    return hyp_hw


# ========== CPA on a single S-box ==========

def run_cpa_for_sbox(traces, plaintexts_int, sbox_num):
    """
    traces: NumPy array of shape (num_traces, trace_len)
    plaintexts_int: list of 64-bit int plaintexts (same order as traces)
    sbox_num: which S-box (1..8)

    For each key guess k in [0..63], we:
      - build X = HW(SBOX_out(PT[i], k)) for all i
      - for each sample j, correlate X with Y_j = traces[:, j]
      - keep the max |correlation| over j as the score of key k

    Returns:
      results: list of (key, max_abs_corr, best_sample_index), sorted by corr desc
    """
    num_traces, trace_len = traces.shape
    print(f"\n[INFO] CPA on S-box {sbox_num} with {num_traces} traces, trace_len={trace_len}")

    # 1) Precompute hypothetical HW matrix for this S-box (shape: 64 x num_traces)
    hyp_hw = precompute_hypothetical_hw_for_sbox(sbox_num, plaintexts_int)

    # 2) Prepare trace matrix Y and center it once
    Y = traces.astype(float)
    Y_mean = np.mean(Y, axis=0)           # per-sample mean
    Yc = Y - Y_mean                       # centered traces
    denom_y = np.sqrt(np.sum(Yc**2, axis=0))  # per-sample norm
    denom_y[denom_y == 0] = np.inf        # avoid division by zero

    results = []

    print(f"\n[INFO] Computing correlations for each key guess on S-box {sbox_num}...")
    for guess_k in range(64):
        X = hyp_hw[guess_k]               # length num_traces
        X_mean = np.mean(X)
        Xc = X - X_mean
        denom_x = np.sqrt(np.sum(Xc**2))
        if denom_x == 0:
            print(f"  S{sbox_num} key={guess_k:02d}: zero variance in X, skipping")
            continue

        # numerator for each sample j: sum_i Xc[i] * Yc[i, j]
        numer = Yc.T @ Xc                 # shape (trace_len,)

        corr_vec = numer / (denom_x * denom_y)  # Pearson correlation per sample
        abs_corr = np.abs(corr_vec)

        best_idx = int(np.argmax(abs_corr))
        best_val = float(abs_corr[best_idx])
        sign_corr = float(corr_vec[best_idx])

        print(f"  S{sbox_num} key={guess_k:02d}: "
              f"max |corr|={best_val:.6f} at sample {best_idx} "
              f"(corr={sign_corr:.6f})")

        results.append((guess_k, best_val, best_idx))

    # sort keys by correlation score (descending)
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ========== main: capture phase + CPA phase ==========

def main():
    # ----- parse command line: ./cpa.py <n_traces> -----
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
        print("[ERROR] No traces captured, aborting CPA.")
        scope.dis()
        target.dis()
        return

    traces = np.vstack(traces_list)
    plaintexts_int = used_plaintexts_int

    # (optional) save combined arrays
    os.makedirs(TRACES_DIR, exist_ok=True)
    np.save(os.path.join(TRACES_DIR, "traces_all_cpa.npy"), traces)
    np.save(os.path.join(TRACES_DIR, "plaintexts_all_cpa.npy"),
            np.array(plaintexts_int, dtype=np.uint64))

    print(f"\n[INFO] Capture done. Traces shape = {traces.shape}")
    print(f"[INFO] Starting CPA phase on all 8 S-boxes.")

    # ----- CPA phase for S-boxes 1..8 -----
    all_results = {}

    for sbox_num in range(1, 9):
        sbox_results = run_cpa_for_sbox(traces, plaintexts_int, sbox_num)
        all_results[sbox_num] = sbox_results

    # print top 5 candidates for each S-box
    print("\n=== CPA top 5 keys per S-box ===")
    candidates_hex = []   # for sboux_out.txt

    for sbox_num in range(1, 9):
        sbox_results = all_results.get(sbox_num, [])
        print(f"\nS-box {sbox_num}:")
        if not sbox_results:
            print("  No valid results.")
            candidates_hex.append([])  # keep indexing consistent
            continue

        top5 = sbox_results[:5]
        row_hex = []
        for rank, (key, max_corr, idx) in enumerate(top5, start=1):
            original_sample = OFFSET + idx * DECIMATE
            print(f"  #{rank}: key=0x{key:02X} (dec={key:2d}), "
                  f"max_abs_corr={max_corr:.6f}, "
                  f"sample={idx} (original ≈ {original_sample})")
            row_hex.append(f"0x{key:02X}")
        candidates_hex.append(row_hex)

    # ----- NEW PART: write Python array of candidates to sbox_out.txt -----
    out_filename = "sbox_out.txt"
    with open(out_filename, "w") as f:
        f.write("CANDIDATES_HEX = [\n")
        for row in candidates_hex:
            # format like ["0x27", "0x2C", ...]
            row_str = ", ".join(f'"{x}"' for x in row)
            f.write(f"    [{row_str}],\n")
        f.write("]\n")
    print(f"\n[INFO] Written S-box key candidates to {out_filename}")

    # cleanup
    scope.dis()
    target.dis()


if __name__ == "__main__":
    main()
