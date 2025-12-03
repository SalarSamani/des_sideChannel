import chipwhisperer as cw

CW_SERIAL = "442031204c5032433130333234313031"
FLASH_ADDR = 0x08000000   # start of flash
READ_LEN   = 16

scope = cw.scope(sn=CW_SERIAL)
scope.default_setup()
target = cw.target(scope)
prog   = cw.programmers.STM32FProgrammer(); prog.scope = scope
stm32  = prog.stm32prog(); stm32.scope = scope

def enter_bootloader():
    stm32.set_boot(True)
    stm32.reset()
    stm32.open_port(baud=9600)
    target.flush()
    target.write('\x7F')
    assert target.read(1) == '\x79'

def can_read_flash():
    # Read Memory (0x11)
    target.write('\x11')
    target.write('\xEE')
    if target.read(1) != '\x79':
        return False

    # Address + checksum
    addr_bytes = FLASH_ADDR.to_bytes(4, 'big')
    checksum = addr_bytes[0] ^ addr_bytes[1] ^ addr_bytes[2] ^ addr_bytes[3]
    target.write(''.join(chr(b) for b in addr_bytes))
    target.write(chr(checksum))
    if target.read(1) != '\x79':
        return False

    # Length-1 and complement (16 bytes)
    N = READ_LEN - 1
    target.write(chr(N))
    target.write(chr(0xFF - N))
    if target.read(1) != '\x79':
        return False

    data = target.read(READ_LEN)
    return len(data) == READ_LEN

def print_status(label):
    if can_read_flash():
        print(label, ": RDP DISABLED (RDP0, flash readable)")
    else:
        print(label, ": RDP ENABLED (RDP1) or read blocked")

def enable_rdp():
    target.write('\x82')
    target.write('\x7D')
    print("Enable RDP ACKs:", repr(target.read(1)), repr(target.read(1)))

def disable_rdp():
    # WARNING: this erases user flash!
    target.write('\x92')
    target.write('\x6D')
    print("Disable RDP ACKs:", repr(target.read(1)), repr(target.read(1)))

# --- sequence ---
enter_bootloader()
print_status("Initial")

enable_rdp()
enter_bootloader()
print_status("After enabling RDP")

disable_rdp()
enter_bootloader()
print_status("After disabling RDP")
