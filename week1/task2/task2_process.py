import numpy as np
import os
import matplotlib.pyplot as plt

def load_and_average(trace_dir):
    """
    Load all .npy traces from trace_dir and compute the sample-by-sample average.
    Returns the average trace as a 1D numpy array.
    """
    files = sorted(f for f in os.listdir(trace_dir) if f.endswith(".npy"))
    if not files:
        raise RuntimeError(f"No .npy files found in directory {trace_dir}")

    avg = None
    count = 0

    for fname in files:
        path = os.path.join(trace_dir, fname)
        trace = np.load(path)

        if avg is None:
            avg = np.zeros_like(trace, dtype=float)

        avg += trace
        count += 1

    avg /= float(count)
    print(f"[INFO] Averaged {count} traces from {trace_dir}")
    return avg

def main():
    # --- 1) Load and average set A and set B ---
    tAavg = load_and_average("set_A")
    tBavg = load_and_average("set_B")

    # Save averages
    np.save("set_A_average.npy", tAavg)
    np.save("set_B_average.npy", tBavg)
    print("[INFO] Saved set_A_average.npy and set_B_average.npy")

    # --- 2) Compute abs(tAavg - tBavg) ---
    diff = np.abs(tAavg - tBavg)
    np.save("trace_difference.npy", diff)
    print("[INFO] Saved trace_difference.npy")

    # --- 3) Plot one trace + abs difference in the same figure ---
    # Use one of the 200 traces (for example the first from set_A)
    trace_files_A = sorted(f for f in os.listdir("set_A") if f.endswith(".npy"))
    if not trace_files_A:
        raise RuntimeError("No traces found in set_A directory")

    example_trace_path = os.path.join("set_A", trace_files_A[0])
    example_trace = np.load(example_trace_path)
    print(f"[INFO] Using example trace: {example_trace_path}")

    x = np.arange(len(example_trace))

    plt.figure(figsize=(12, 4))
    plt.plot(x, example_trace, label="Example trace (from set A)")
    plt.plot(x, diff, label="abs(tAavg - tBavg)")
    plt.xlabel("Sample index")
    plt.ylabel("Power (ADC units)")
    plt.title("Example power trace and |tAavg - tBavg|")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("trace_difference.png", dpi=300)
    plt.close()
    print("[INFO] Saved plot to trace_difference.png")

if __name__ == "__main__":
    main()
