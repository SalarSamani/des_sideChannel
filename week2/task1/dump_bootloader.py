import chipwhisperer as cw
import time

# Your CW-Lite serial
CW_SERIAL = "442031204c5032433130333234313031"

# STM32F303 bootloader (system memory) region
BOOT_BASE  = 0x1FFFD800   # start address
BOOT_SIZE  = 8192         # 8 KB total
CHUNK_SIZE = 256          # read 256 bytes at a time

scope = None
target = None
stm32 = None

def connect():
    global scope, target, stm32
    scope = cw.scope(sn=CW_SERIAL)
    scope.default_setup()
    target = cw.target(scope)

    prog = cw.programmers.STM32FProgrammer()
    prog.scope = scope
    stm32 = prog.stm32prog()
    stm32.scope = scope

    print("Connected to CW-Lite.")

def enter_bootloader():
    """BOOT0 = 1, reset, open UART, do 0x7F/0x79 handshake."""
    stm32.set_boot(True)          # BOOT0 = 1 -> system memory
    stm32.reset()
    stm32.open_port(baud=9600)
    target.flush()

    target.write('\x7F')          # sync byte
    resp = target.read(1)
    assert resp == '\x79', f"sync failed, got {repr(resp)}"
    print("Bootloader ACK (0x79) received.")

def disable_rdp():
    """Send Readout Unprotect (0x92 0x6D).
       WARNING: this mass-erases flash and sets RDP = 0."""
    print("Disabling RDP (this WILL erase user flash!)")
    target.write('\x92')
    target.write('\x6D')

    ack1 = target.read(1)         # first ACK
    ack2 = target.read(1)         # second ACK after erase
    print("Unprotect ACKs:", repr(ack1), repr(ack2))

    # After this, the chip resets itself.
    # Keep BOOT0 = 1 and we’ll reset again via enter_bootloader().
    time.sleep(0.1)

def read_chunk(addr, size=CHUNK_SIZE):
    """Read `size` bytes from `addr` using Read Memory (0x11)."""
    # 1) Send Read Memory command: 0x11 + 0xEE
    target.write('\x11')
    target.write('\xEE')
    r = target.read(1)
    assert r == '\x79', f"No ACK after Read Memory cmd at 0x{addr:08X}, got {repr(r)}"

    # 2) Send 4-byte address (big-endian) + XOR checksum
    addr_bytes = addr.to_bytes(4, 'big')
    checksum = addr_bytes[0] ^ addr_bytes[1] ^ addr_bytes[2] ^ addr_bytes[3]
    target.write(''.join(chr(b) for b in addr_bytes))
    target.write(chr(checksum))
    r = target.read(1)
    assert r == '\x79', f"No ACK after address at 0x{addr:08X}, got {repr(r)}"

    # 3) Send length-1 and its complement (N=255 -> 256 bytes)
    N = size - 1
    target.write(chr(N))
    target.write(chr(0xFF - N))
    r = target.read(1)
    assert r == '\x79', f"No ACK after length at 0x{addr:08X}, got {repr(r)}"

    # 4) Read `size` data bytes
    data_str = target.read(size)
    if len(data_str) != size:
        raise IOError(f"Short read at 0x{addr:08X}: got {len(data_str)} bytes")
    return bytes(ord(c) for c in data_str)

def dump_bootloader():
    boot = bytearray()
    for offset in range(0, BOOT_SIZE, CHUNK_SIZE):
        addr = BOOT_BASE + offset
        chunk = read_chunk(addr)
        boot.extend(chunk)
        print(f"Read {CHUNK_SIZE} bytes from 0x{addr:08X}")
    with open("bootloader.bin", "wb") as f:
        f.write(boot)
    print(f"Done. Dumped {len(boot)} bytes to bootloader.bin")

if __name__ == "__main__":
    connect()

    # 1) Enter bootloader with RDP1
    enter_bootloader()

    # 2) Disable readout protection (RDP -> 0, flash erased)
    disable_rdp()

    # 3) Re-enter bootloader with RDP0
    enter_bootloader()

    # 4) Dump 8 KB ROM bootloader
    dump_bootloader()
