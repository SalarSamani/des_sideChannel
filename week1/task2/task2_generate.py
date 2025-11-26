import chipwhisperer as cw
import time
import numpy as np
import os

scope = None
target = None

# Capture parameters
SAMPLES = 13420
DECIMATE = 2
OFFSET = 0

def init():
    """Connect to ChipWhisperer and target."""
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
    """Reset the STM32 target."""
    global scope
    scope.io.nrst = 'low'
    time.sleep(0.05)
    scope.io.nrst = 'high_z'
    time.sleep(0.05)

def setup_adc():
    """Set ADC parameters for each capture."""
    global scope
    scope.adc.samples = SAMPLES
    scope.adc.decimate = DECIMATE
    scope.adc.offset = OFFSET
    scope.adc.presamples = 0
    scope.adc.timeout = 2

def capture_one_trace(plaintext_bytes):
    """Capture one power trace for the given 8-byte plaintext."""
    global scope, target

    setup_adc()
    scope.arm()

    # Send plaintext and read ciphertext (like your previous code)
    target.simpleserial_write('d', plaintext_bytes)
    ciphertext = target.simpleserial_read('r', 8)
    print("  Ciphertext =", ciphertext.hex())

    if scope.capture():
        print("[ERROR] Capture timed out")
        return None

    trace = np.array(scope.get_last_trace(), dtype=float)
    print("  Trace length =", len(trace))
    return trace

def read_plaintexts_from_file(filename):
    """
    Read lines like:
    0x00000000XXXXXXXX
    0xFFFFFFFFYYYYYYYY
    and convert to 8-byte plaintexts.
    """
    plaintexts = []
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue  # skip empty lines
            # interpret line as hex (handles with or without '0x')
            value = int(line, 16)
            pt_bytes = value.to_bytes(8, byteorder="big", signed=False)
            plaintexts.append(pt_bytes)
    return plaintexts

def capture_set(txt_file, out_dir, prefix):
    """
    Read plaintexts from txt_file,
    capture one trace for each, and save as .npy in out_dir.
    """
    os.makedirs(out_dir, exist_ok=True)

    plaintexts = read_plaintexts_from_file(txt_file)
    print(f"[INFO] Capturing {len(plaintexts)} traces for {txt_file}")

    for i, pt in enumerate(plaintexts):
        print(f"\n[INFO] Capturing trace {i+1} / {len(plaintexts)} for set {prefix}")
        trace = capture_one_trace(pt)
        if trace is None:
            print("[WARN] Skipping this trace (capture failed)")
            continue

        filename = os.path.join(out_dir, f"trace_{prefix}_{i:03d}.npy")
        np.save(filename, trace)
        print(f"[INFO] Saved trace to {filename}")

def main():
    init()
    reset_target()

    # --- Capture for set A ---
    capture_set("set_A.txt", "set_A", "A")

    # --- Capture for set B ---
    capture_set("set_B.txt", "set_B", "B")

    print("\n[INFO] Done capturing traces for Task 2.")
    print("[INFO] No PNG files were created in this step.")

if __name__ == "__main__":
    main()
