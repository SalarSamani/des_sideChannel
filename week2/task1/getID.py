import chipwhisperer as cw

# Connect to your CW-Lite
scope = cw.scope(sn="442031204c5032433130333234313031")
scope.default_setup()
target = cw.target(scope)
prog = cw.programmers.STM32FProgrammer()
prog.scope = scope
stm32 = prog.stm32prog()
stm32.scope = scope

# Enter ROM bootloader
stm32.set_boot(True)           # BOOT0 = 1
stm32.reset()
stm32.open_port(baud=9600)
target.flush()

# Sync (0x7F -> 0x79)
target.write('\x7F')
assert target.read(1) == '\x79'

# Get ID command: 0x02 + 0xFD
target.write('\x02')
target.write('\xFD')
assert target.read(1) == '\x79'    # ACK

n = ord(target.read(1)) + 1       # length + 1
pid = target.read(n)
assert target.read(1) == '\x79'    # final ACK

pid_bytes = [ord(c) for c in pid]
print("PID bytes:", ["0x%02X" % b for b in pid_bytes])
if len(pid_bytes) >= 2:
    chip_id = (pid_bytes[0] << 8) | pid_bytes[1]
    print("Chip ID: 0x%04X" % chip_id)
