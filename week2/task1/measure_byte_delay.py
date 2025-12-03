import chipwhisperer as cw
import time
import statistics

CW_SERIAL    = "442031204c5032433130333234313031"
NUM_SAMPLES  = 50    # how many measurements

scope = None
target = None
stm32 = None


def connect():
    global scope, target, stm32

    print("[*] Connecting to CW-Lite...")
    scope = cw.scope(sn=CW_SERIAL)
    scope.default_setup()

    target = cw.target(scope)

    prog = cw.programmers.STM32FProgrammer()
    prog.scope = scope
    stm32 = prog.stm32prog()
    stm32.scope = scope


def enter_bootloader():
    """BOOT0=1 + 0x7F/0x79 sync."""
    stm32.set_boot(True)
    stm32.reset()
    stm32.open_port(baud=9600)
    target.flush()

    target.write('\x7F')
    resp = target.read(1)
    if resp != '\x79':
        raise RuntimeError("Bootloader sync failed, got %r" % (resp,))


def disable_rdp():
    """
    Disable readout protection (RDP0) using 0x92 0x6D.

    ⚠ This will mass-erase user flash.
    """
    print("[*] Disabling RDP (going to RDP0, flash will be erased)...")
    target.write('\x92')
    target.write('\x6D')

    ack1 = target.read(1)
    ack2 = target.read(1)
    print("    RDP disable ACKs:", repr(ack1), repr(ack2))

    # Chip resets after unprotect
    time.sleep(0.1)


def measure_one():
    """
    Measure time from sending 0x11 0xEE until receiving ACK (0x79).

    That’s:
      - 2 bytes host -> STM32
      - 1 byte STM32 -> host
    """

    t0 = time.perf_counter()

    # Send Read Memory command + complement
    target.write('\x11')
    target.write('\xEE')

    # Wait for first response (ACK when RDP0)
    ack = target.read(1)

    t1 = time.perf_counter()

    if ack != '\x79':
        print("  WARNING: expected ACK 0x79, got", repr(ack))

    dt = t1 - t0   # total time for 3 bytes
    return dt


def main():
    connect()

    # First enter bootloader and force RDP0
    enter_bootloader()
    disable_rdp()

    print("[*] Now measuring with RDP0 (0x11 should get ACK 0x79).")

    times = []

    for i in range(NUM_SAMPLES):
        # fresh bootloader session for each measurement
        enter_bootloader()
        dt = measure_one()
        per_byte = dt / 3.0
        times.append(per_byte)

        print("Sample %3d: total = %.6f s  ->  per byte ≈ %.6f s"
              % (i + 1, dt, per_byte))

    avg = statistics.mean(times)
    std = statistics.pstdev(times) if len(times) > 1 else 0.0

    print("\n[*] Average per-byte time over %d samples:" % NUM_SAMPLES)
    print("    mean = %.6f s  (%.3f ms)" % (avg, avg * 1000.0))
    print("    std  = %.6f s  (%.3f ms)" % (std, std * 1000.0))


if __name__ == "__main__":
    main()
