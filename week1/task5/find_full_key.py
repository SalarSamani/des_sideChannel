#!/usr/bin/env python3
import os
import sys
import itertools
from Crypto.Cipher import DES

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

SBOX_OUT_FILE = os.path.join(os.path.dirname(__file__), ".", "sbox_out.txt")

# Default: how many candidates per S-box row to use (1..5)
DEFAULT_TOP_N = 3

# Known plaintext and ciphertext (hex)
PLAINTEXT_HEX = "4142434445464748"
CIPHERTEXT_HEX = "ef770c97ad062c75"

# Inverse PC1: for each 64-bit position i (0..63),
# PC1_INV[i] = position in 56-bit key (1..56) OR 0 if this is a parity bit.
PC1_INV = [
 8, 16, 24, 56, 52, 44, 36,  0,
 7, 15, 23, 55, 51, 43, 35,  0,
 6, 14, 22, 54, 50, 42, 34,  0,
 5, 13, 21, 53, 49, 41, 33,  0,
 4, 12, 20, 28, 48, 40, 32,  0,
 3, 11, 19, 27, 47, 39, 31,  0,
 2, 10, 18, 26, 46, 38, 30,  0,
 1,  9, 17, 25, 45, 37, 29,  0,
]

# Inverse of PC2 (56 entries). 0 means "bit was dropped by PC2".
PC2_INV = [
 5, 24,  7, 16,  6, 10, 20, 18,
 0, 12,  3, 15, 23,  1,  9, 19,
 2,  0, 14, 22, 11,  0, 13,  4,
 0, 17, 21,  8, 47, 31, 27, 48,
35, 41,  0, 46, 28,  0, 39, 32,
25, 44,  0, 37, 34, 43, 29, 36,
38, 45, 33, 26, 42,  0, 30, 40,
]


# ----------------------------------------------------------------------
# Bit helpers
# ----------------------------------------------------------------------

def int_to_bits(x, n):
    """Convert integer x to list of n bits (MSB first)."""
    return [(x >> (n - 1 - i)) & 1 for i in range(n)]


def bits_to_int(bits):
    """Convert list of bits (MSB first) to integer."""
    v = 0
    for b in bits:
        v = (v << 1) | b
    return v


# ----------------------------------------------------------------------
# Step 1: load S-box candidates from sbox_out.txt
# ----------------------------------------------------------------------

def load_candidates_from_sbox_out(path=SBOX_OUT_FILE):
    """
    Load CANDIDATES_HEX from sbox_out.txt, which contains:

    CANDIDATES_HEX = [
        ["0x27", "0x38", "0x2C", "0x25", "0x39"],
        ...
    ]
    """
    ns = {}
    with open(path, "r") as f:
        code = f.read()
    exec(code, {}, ns)

    if "CANDIDATES_HEX" not in ns:
        raise ValueError("CANDIDATES_HEX not found in sbox_out.txt")

    cand_hex = ns["CANDIDATES_HEX"]
    candidates = [[int(x, 16) for x in row] for row in cand_hex]
    return cand_hex, candidates


# ----------------------------------------------------------------------
# Step 2: generate 48-bit K1 candidates from S-box candidates
# ----------------------------------------------------------------------

def generate_k1_ints(candidates, top_n):
    """
    candidates: 2D list of ints [8 x 5] from sbox_out.txt
    top_n: number of candidates per S-box row to use (1..5)

    Yields 48-bit K1 integers.
    K1 layout: [S1 (MSB 6 bits)] ... [S8 (LSB 6 bits)]
    """
    if not (1 <= top_n <= 5):
        raise ValueError("top_n must be between 1 and 5")

    per_sbox_lists = [row[:top_n] for row in candidates]  # 8 rows

    for combo in itertools.product(*per_sbox_lists):
        k1 = 0
        for sbox_index, subkey_6bit in enumerate(combo):
            shift = (7 - sbox_index) * 6
            k1 |= (subkey_6bit & 0x3F) << shift
        yield k1


# ----------------------------------------------------------------------
# Step 3: expand 48-bit K1 to all possible 56-bit (C1||D1) using PC2_INV
# ----------------------------------------------------------------------

def expand_k1_to_56(k1_int):
    """
    From one 48-bit K1 candidate, build all possible 56-bit pre-PC2 values.

    - Known bits (PC2_INV[i] != 0) are taken from K1.
    - Unknown bits (PC2_INV[i] == 0) are filled with all 2^8 combinations.
    """
    k1_bits = int_to_bits(k1_int, 48)

    template = []
    for i in range(56):
        out_pos = PC2_INV[i]
        if out_pos == 0:
            template.append(None)
        else:
            template.append(k1_bits[out_pos - 1])

    unknown_positions = [i for i, b in enumerate(template) if b is None]
    m = len(unknown_positions)
    if m != 8:
        print(f"[WARN] Expected 8 unknown bits, found {m}.")

    for pattern in range(1 << m):
        bits = template[:]
        for idx, pos in enumerate(unknown_positions):
            bit_val = (pattern >> (m - 1 - idx)) & 1
            bits[pos] = bit_val
        yield bits_to_int(bits)


# ----------------------------------------------------------------------
# Step 4: reverse round-1 shift (C1||D1 -> C0||D0)
# ----------------------------------------------------------------------

def reverse_round1_shift(k56_int):
    """
    k56_int: 56-bit candidate that represents C1||D1 (after round-1 left shift).
    We reverse the shift to get C0||D0 by rotating each 28-bit half right by 1 bit.
    """
    bits = int_to_bits(k56_int, 56)
    C1 = bits[:28]
    D1 = bits[28:]

    C0 = [C1[-1]] + C1[:-1]
    D0 = [D1[-1]] + D1[:-1]

    return C0 + D0  # list of 56 bits


# ----------------------------------------------------------------------
# Step 5: apply PC1_INV to go from 56-bit (C0||D0) to 64-bit key K
# ----------------------------------------------------------------------

def apply_pc1_inv(cd0_bits):
    """
    cd0_bits: list of 56 bits (C0||D0).

    Use PC1_INV to reconstruct the 64-bit full key:
      - PC1_INV[i] == 0 -> parity bit = 0
      - else take bit from cd0_bits[PC1_INV[i] - 1]
    """
    if len(cd0_bits) != 56:
        raise ValueError("cd0_bits must have length 56")

    key64_bits = []
    for i in range(64):
        pos56 = PC1_INV[i]
        if pos56 == 0:
            key64_bits.append(0)
        else:
            key64_bits.append(cd0_bits[pos56 - 1])

    return bits_to_int(key64_bits)


# ----------------------------------------------------------------------
# Step 6: full search pipeline and DES test
# ----------------------------------------------------------------------

def recover_key_from_sbox_out(top_n):
    plaintext = bytes.fromhex(PLAINTEXT_HEX)
    target_cipher = bytes.fromhex(CIPHERTEXT_HEX)

    # Load S-box candidates
    cand_hex, candidates = load_candidates_from_sbox_out()
    print("[INFO] Loaded CANDIDATES_HEX from sbox_out.txt:")
    for i, row in enumerate(cand_hex, start=1):
        print(f"  S-box {i}: {row}")
    print(f"[INFO] Using top {top_n} candidates per S-box.")

    tested_56 = 0
    tested_K1 = 0

    for k1_int in generate_k1_ints(candidates, top_n):
        tested_K1 += 1

        # For each K1, generate all possible 56-bit values
        for k56_int in expand_k1_to_56(k1_int):
            tested_56 += 1

            # Reverse round-1 shift to get C0||D0
            cd0_bits = reverse_round1_shift(k56_int)

            # Apply PC1_INV to get 64-bit key with parity bits = 0
            key64_int = apply_pc1_inv(cd0_bits)
            key_bytes = key64_int.to_bytes(8, "big")

            # Test this key with DES (ECB)
            cipher = DES.new(key_bytes, DES.MODE_ECB)
            out = cipher.encrypt(plaintext)

            if out == target_cipher:
                print("\n[+] Found matching key!")
                print(f"    Key (hex) = 0x{key64_int:016X}")
                print(f"[INFO] Tested {tested_56} candidate 56-bit keys (from {tested_K1} K1s).")
                return key64_int

    print(f"[INFO] Finished search.")
    print(f"[INFO] Tested {tested_56} candidate 56-bit keys (from {tested_K1} K1s).")
    print("[INFO] No matching key found.")
    return None


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    # Usage:
    #   python3 recover_key_from_sbox_out.py         -> uses DEFAULT_TOP_N
    #   python3 recover_key_from_sbox_out.py 3       -> uses top_n = 3
    if len(sys.argv) == 1:
        top_n = DEFAULT_TOP_N
    elif len(sys.argv) == 2:
        try:
            top_n = int(sys.argv[1])
        except ValueError:
            print("[ERROR] top_n must be an integer between 1 and 5.")
            sys.exit(1)
    else:
        print(f"Usage: {sys.argv[0]} [top_n_candidates_per_sbox]")
        print("  top_n_candidates_per_sbox must be 1, 2, 3, 4, or 5")
        sys.exit(1)

    if not (1 <= top_n <= 5):
        print("[ERROR] top_n must be between 1 and 5.")
        sys.exit(1)

    key = recover_key_from_sbox_out(top_n)
    if key is not None:
        print(f"[RESULT] Full 64-bit key (parity bits = 0): 0x{key:016X}")


if __name__ == "__main__":
    main()
