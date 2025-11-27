#  Helper functions 

def int_to_bits(x, n):
    """Convert integer x to list of n bits (MSB first)."""
    bits = []
    for i in range(n):
        # take bit from most-significant to least-significant
        bit = (x >> (n - 1 - i)) & 1
        bits.append(bit)
    return bits

def bits_to_int(bits):
    """Convert list of bits (MSB first) to integer."""
    value = 0
    for b in bits:
        value = (value << 1) | b
    return value

def permute(bits, table):
    """Apply a DES-style permutation table (1-based indices)."""
    return [bits[i - 1] for i in table]


#  DES tables 

# Initial permutation IP for the 64-bit plaintext
IP = [
    58, 50, 42, 34, 26, 18, 10,  2,
    60, 52, 44, 36, 28, 20, 12,  4,
    62, 54, 46, 38, 30, 22, 14,  6,
    64, 56, 48, 40, 32, 24, 16,  8,
    57, 49, 41, 33, 25, 17,  9,  1,
    59, 51, 43, 35, 27, 19, 11,  3,
    61, 53, 45, 37, 29, 21, 13,  5,
    63, 55, 47, 39, 31, 23, 15,  7
]

# Expansion E: 32-bit R0 -> 48 bits
E_TABLE = [
    32,  1,  2,  3,  4,  5,
     4,  5,  6,  7,  8,  9,
     8,  9, 10, 11, 12, 13,
    12, 13, 14, 15, 16, 17,
    16, 17, 18, 19, 20, 21,
    20, 21, 22, 23, 24, 25,
    24, 25, 26, 27, 28, 29,
    28, 29, 30, 31, 32,  1
]

# (P table is not needed for sbox_out, but you gave it, so here it is for later use)
P_TABLE = [
    16,  7, 20, 21,
    29, 12, 28, 17,
     1, 15, 23, 26,
     5, 18, 31, 10,
     2,  8, 24, 14,
    32, 27,  3,  9,
    19, 13, 30,  6,
    22, 11,  4, 25
]

# Key permutation tables (PC-1 and PC-2) – used only in the test to build K1 from K
PC1 = [
    57, 49, 41, 33, 25, 17,  9,
     1, 58, 50, 42, 34, 26, 18,
    10,  2, 59, 51, 43, 35, 27,
    19, 11,  3, 60, 52, 44, 36,
    63, 55, 47, 39, 31, 23, 15,
     7, 62, 54, 46, 38, 30, 22,
    14,  6, 61, 53, 45, 37, 29,
    21, 13,  5, 28, 20, 12,  4
]

PC2 = [
    14, 17, 11, 24,  1,  5,
     3, 28, 15,  6, 21, 10,
    23, 19, 12,  4, 26,  8,
    16,  7, 27, 20, 13,  2,
    41, 52, 31, 37, 47, 55,
    30, 40, 51, 45, 33, 48,
    44, 49, 39, 56, 34, 53,
    46, 42, 50, 36, 29, 32
]

# S-boxes, each is a flat list of 64 entries
S1 = [14,  4, 13,  1,  2, 15, 11,  8,  3, 10,  6, 12,  5,  9,  0,  7,
       0, 15,  7,  4, 14,  2, 13,  1, 10,  6, 12, 11,  9,  5,  3,  8,
       4,  1, 14,  8, 13,  6,  2, 11, 15, 12,  9,  7,  3, 10,  5,  0,
      15, 12,  8,  2,  4,  9,  1,  7,  5, 11,  3, 14, 10,  0,  6, 13]

S2 = [15,  1,  8, 14,  6, 11,  3,  4,  9,  7,  2, 13, 12,  0,  5, 10,
       3, 13,  4,  7, 15,  2,  8, 14, 12,  0,  1, 10,  6,  9, 11,  5,
       0, 14,  7, 11, 10,  4, 13,  1,  5,  8, 12,  6,  9,  3,  2, 15,
      13,  8, 10,  1,  3, 15,  4,  2, 11,  6,  7, 12,  0,  5, 14,  9]

S3 = [10,  0,  9, 14,  6,  3, 15,  5,  1, 13, 12,  7, 11,  4,  2,  8,
      13,  7,  0,  9,  3,  4,  6, 10,  2,  8,  5, 14, 12, 11, 15,  1,
      13,  6,  4,  9,  8, 15,  3,  0, 11,  1,  2, 12,  5, 10, 14,  7,
       1, 10, 13,  0,  6,  9,  8,  7,  4, 15, 14,  3, 11,  5,  2, 12]

S4 = [ 7, 13, 14,  3,  0,  6,  9, 10,  1,  2,  8,  5, 11, 12,  4, 15,
      13,  8, 11,  5,  6, 15,  0,  3,  4,  7,  2, 12,  1, 10, 14,  9,
      10,  6,  9,  0, 12, 11,  7, 13, 15,  1,  3, 14,  5,  2,  8,  4,
       3, 15,  0,  6, 10,  1, 13,  8,  9,  4,  5, 11, 12,  7,  2, 14]

S5 = [ 2, 12,  4,  1,  7, 10, 11,  6,  8,  5,  3, 15, 13,  0, 14,  9,
      14, 11,  2, 12,  4,  7, 13,  1,  5,  0, 15, 10,  3,  9,  8,  6,
       4,  2,  1, 11, 10, 13,  7,  8, 15,  9, 12,  5,  6,  3,  0, 14,
      11,  8, 12,  7,  1, 14,  2, 13,  6, 15,  0,  9, 10,  4,  5,  3]

S6 = [12,  1, 10, 15,  9,  2,  6,  8,  0, 13,  3,  4, 14,  7,  5, 11,
      10, 15,  4,  2,  7, 12,  9,  5,  6,  1, 13, 14,  0, 11,  3,  8,
       9, 14, 15,  5,  2,  8, 12,  3,  7,  0,  4, 10,  1, 13, 11,  6,
       4,  3,  2, 12,  9,  5, 15, 10, 11, 14,  1,  7,  6,  0,  8, 13]

S7 = [ 4, 11,  2, 14, 15,  0,  8, 13,  3, 12,  9,  7,  5, 10,  6,  1,
      13,  0, 11,  7,  4,  9,  1, 10, 14,  3,  5, 12,  2, 15,  8,  6,
       1,  4, 11, 13, 12,  3,  7, 14, 10, 15,  6,  8,  0,  5,  9,  2,
       6, 11, 13,  8,  1,  4, 10,  7,  9,  5,  0, 15, 14,  2,  3, 12]

S8 = [13,  2,  8,  4,  6, 15, 11,  1, 10,  9,  3, 14,  5,  0, 12,  7,
       1, 15, 13,  8, 10,  3,  7,  4, 12,  5,  6, 11,  0, 14,  9,  2,
       7, 11,  4,  1,  9, 12, 14,  2,  0,  6, 10, 13, 15,  3,  5,  8,
       2,  1, 14,  7,  4, 10,  8, 13, 15, 12,  9,  0,  3,  5,  6, 11]

SBOXES = [S1, S2, S3, S4, S5, S6, S7, S8]


# sbox_out implementation 

def sbox_out(sbox_num, plaintext, guess_k1):
    """
    sbox_num: which S-box (1..8)
    plaintext: 64-bit integer (original DES plaintext)
    guess_k1: 6-bit integer (0..63), guessed subkey bits for this S-box

    Returns: integer 0..15 (4-bit output of that S-box in round 1).
    """

    # 1) Apply initial permutation IP to plaintext ---
    pt_bits = int_to_bits(plaintext, 64)
    ip_bits = permute(pt_bits, IP)

    # Split into L0, R0 (we only need R0)
    R0 = ip_bits[32:]   # last 32 bits

    # 2) Expand R0 to 48 bits using E-table ---
    e_bits = permute(R0, E_TABLE)

    # 3) Take the 6-bit chunk for this S-box ---
    start = (sbox_num - 1) * 6
    B = e_bits[start:start + 6]

    # 4) XOR with guessed 6-bit subkey for this S-box ---
    guess_bits = int_to_bits(guess_k1, 6)
    B_xor = []
    for b, k in zip(B, guess_bits):
        B_xor.append(b ^ k)

    # 5) Look up in the S-box ---
    # row = first and last bit; col = middle 4 bits
    row = (B_xor[0] << 1) | B_xor[5]
    col = (B_xor[1] << 3) | (B_xor[2] << 2) | (B_xor[3] << 1) | B_xor[4]
    index = row * 16 + col

    sbox = SBOXES[sbox_num - 1]
    value = sbox[index]   # integer 0..15

    return value


def left_shift(bits, n):
    return bits[n:] + bits[:n]

def compute_K1_bits_from_key(key64_int):
    """Compute round-1 subkey K1 (48 bits) from 64-bit DES key."""
    key_bits = int_to_bits(key64_int, 64)
    k_plus = permute(key_bits, PC1)   # 56 bits
    C0 = k_plus[:28]
    D0 = k_plus[28:]
    # Round 1: shift by 1
    C1 = left_shift(C0, 1)
    D1 = left_shift(D0, 1)
    CD1 = C1 + D1
    K1_bits = permute(CD1, PC2)       # 48 bits
    return K1_bits

if __name__ == "__main__":
    # Example from your question:
    PT = int("0123456789ABCDEF", 16)
    K  = int("133457799BBCDFF1", 16)

    # Build K1 from K (no hard-coded K1)
    K1_bits = compute_K1_bits_from_key(K)

    # For each S-box, take its 6 bits from K1 and test sbox_out
    all_s_bits = []
    for sbox_num in range(1, 9):
        k1_chunk = K1_bits[(sbox_num - 1) * 6 : sbox_num * 6]
        guess_k1 = bits_to_int(k1_chunk)

        val = sbox_out(sbox_num, PT, guess_k1)
        val_bits = int_to_bits(val, 4)
        all_s_bits.extend(val_bits)

        print(f"S{sbox_num} =", ''.join(str(b) for b in val_bits))

    print("All S-box outputs concatenated:")
    print(''.join(str(b) for b in all_s_bits))
