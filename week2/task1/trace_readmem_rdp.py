import chipwhisperer as cw
import time
import numpy as np
import matplotlib.pyplot as plt

CW_SERIAL = "442031204c5032433130333234313031"

scope = None
target = None
stm32 = None


def init():
    """Connect to CW-Lite + STM32 bootloader (no glitch, just power trace)."""
    global scope, target, stm32

    scope = cw.scope(sn=CW_SERIAL)
    scope.default_setup()
    target = cw.target(scope)

    prog = cw.programmers.STM32FProgrammer()
    prog.scope = scope
    stm32 = prog.stm32prog()
    stm32.scope = scope

    print("[INFO] Found ChipWhisperer and STM32 target 😄")

    # Make capture window longer by slowing ADC a bit (optional but helpful)
    scope.clock.adc_mul = 1          # 1 * 7.37 MHz instead of 4 * 7.37 MHz


def enter_bootloader():
    """BOOT0 = 1 + 0x7F/0x79 sync into ROM bootloader."""
    stm32.set_boot(True)          # BOOT0 = 1 -> system memory
    stm32.reset()
    stm32.open_port(baud=9600)
    target.flush()

    target.write('\x7F')
    resp = target.read(1)
    if resp not in ('\x79', 'y'):
        raise RuntimeError(f"Bootloader sync failed, got {repr(resp)}")
    print("[INFO] Bootloader ACK (0x79) received.")


def disable_rdp_to_rdp0():
    """
    Send Readout Unprotect (0x92 0x6D) so RDP = 0.

    ⚠ This erases user flash.
    """
    print("[INFO] Disabling RDP (Readout Unprotect, going to RDP0)...")
    target.write('\x92')
    target.write('\x6D')

    ack1 = target.read(1)
    ack2 = target.read(1)
    print("      Unprotect ACKs:", repr(ack1), repr(ack2))


def capture_readmem_trace():
    """
    Capture one power trace while we:
      - send 0x11
      - send 0xEE (complement)
      - get ACK (0x79) in RDP0

    ADC settings:
      samples  = 24400
      decimate = 1
      offset   = 0
    Trigger:
      rising edge on TIO2 (UART TX) at start of 0x11.
    """
    global scope, target

    # ADC config
    scope.adc.samples    = 24400
    scope.adc.decimate   = 50
    scope.adc.offset     = 0
    scope.adc.presamples = 0
    scope.adc.timeout    = 2
    scope.adc.basic_mode = "rising_edge"   # how to interpret trigger

    # Trigger on UART TX (TIO2) instead of TIO4
    scope.trigger.triggers = "tio2"

    print("\n[INFO] ADC config:")
    print("  samples  =", scope.adc.samples)
    print("  decimate =", scope.adc.decimate)
    print("  offset   =", scope.adc.offset)
    print("  trigger  =", scope.trigger.triggers, "(rising_edge)")

    # Fresh bootloader session with RDP0
    enter_bootloader()

    # Arm scope BEFORE sending 0x11 so first TX edge triggers capture
    scope.arm()

    # --- happens while ADC is recording ---
    target.write('\x11')
    target.write('\xEE')

    # Wait for ACK from bootloader (should be 0x79 / 'y' in RDP0)
    ack = target.read(1)
    print("  Got response to 0x11/0xEE:", repr(ack))

    # Wait for capture to complete
    if scope.capture():
        print("[ERROR] Capture timed out.")
        return

    trace = np.array(scope.get_last_trace(), dtype=float)
    print("[INFO] Trace length =", len(trace))

    # Save raw data
    np.save("readmem_trace.npy", trace)
    print("[INFO] Saved raw trace to readmem_trace.npy")

    # Plot and save PNG
    plt.figure(figsize=(10, 3))
    x = np.arange(len(trace))
    plt.plot(x, trace, linewidth=0.6)
    plt.title("Power trace – Read Memory command (0x11 0xEE, RDP0)")
    plt.xlabel("Sample index")
    plt.ylabel("Power (ADC units)")

    step_tick = max(1, len(trace) // 20)
    tick_positions = np.arange(0, len(trace) + 1, step_tick)
    plt.xticks(tick_positions, rotation=45)

    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("readmem_trace.png", dpi=300)
    plt.close()
    print("[INFO] Saved plot to readmem_trace.png")


def main():
    init()

    # 1) Enter bootloader & force RDP0 so 0x11 gets ACK
    enter_bootloader()
    disable_rdp_to_rdp0()

    # 2) Capture one trace around 0x11 + ACK
    capture_readmem_trace()


if __name__ == "__main__":
    main()

