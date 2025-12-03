#!/usr/bin/env bash
set -euo pipefail

BIN="$1"
if [ -z "$BIN" ]; then
  echo "Usage: $0 bootloader.bin"
  exit 1
fi

# address where bootloader.bin was read from
LOAD_ADDR=0x1FFFD800

# output names
ELF="${BIN%.bin}.elf"
DISASM="${BIN%.bin}_disasm.s"

# tools
OBJCOPY=arm-none-eabi-objcopy
OBJDUMP=arm-none-eabi-objdump

# check tools
command -v "$OBJCOPY" >/dev/null 2>&1 || { echo "$OBJCOPY not found. Install binutils-arm-none-eabi."; exit 2; }
command -v "$OBJDUMP" >/dev/null 2>&1 || { echo "$OBJDUMP not found. Install binutils-arm-none-eabi."; exit 2; }

echo "Converting $BIN -> $ELF (load address $LOAD_ADDR)..."
"$OBJCOPY" -I binary -O elf32-littlearm --binary-architecture=arm --set-start="$LOAD_ADDR" "$BIN" "$ELF"

echo "Disassembling $ELF -> $DISASM (force Thumb)..."
"$OBJDUMP" -D -M force-thumb "$ELF" > "$DISASM"

echo "Done."
echo "ELF: $ELF"
echo "Disassembly: $DISASM"
