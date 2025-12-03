import chipwhisperer as cw

scope = None
target = None
stm32 = None

# Connect to your CW-Lite
def connect():
    global scope, target, stm32
    scope = cw.scope(sn="442031204c5032433130333234313031")  # your serial
    scope.default_setup()
    target = cw.target(scope)
    prog = cw.programmers.STM32FProgrammer()
    prog.scope = scope
    stm32 = prog.stm32prog()
    stm32.scope = scope
    print("Connected to CW-Lite.")

# Reboot into bootloader and enable UART bootloader
def reset_in_bootloader():
    global stm32, target
    stm32.set_boot(True)      # set BOOT0 = 1
    stm32.reset()
    stm32.open_port(baud=9600)
    target.flush()
    target.write(b'\x7F')     # send sync byte (must be bytes!)
    resp = target.read(1)
    assert resp == b'\x79', f"Bootloader not responding (got {resp})"
    print("Bootloader active (ACK received).")

# Read chip ID
def read_chip_id():
    global target
    target.write(b'\x02\xFD')   # Get ID command (and complement)
    ack = target.read(1)
    assert ack == b'\x79', f"No ACK after Get ID command (got {ack})"
    n = target.read(1)[0] + 1   # length byte + 1
    chip_id = target.read(n)
    target.read(1)              # final ACK
    print("Chip ID:", chip_id.hex())

# --- Run sequence ---
connect()
reset_in_bootloader()
read_chip_id()

