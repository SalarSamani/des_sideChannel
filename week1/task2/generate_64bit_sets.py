import random

def generate_unique_lsb(count):
    """Generate 'count' unique random 32-bit values."""
    lsbs = set()
    while len(lsbs) < count:
        lsbs.add(random.getrandbits(32))
    return list(lsbs)

def main():
    count = 100

    # Generate 100 unique 32-bit random values for each set
    lsbs_A = generate_unique_lsb(count)
    lsbs_B = generate_unique_lsb(count)

    # Ensure they don't overlap
    while set(lsbs_A) & set(lsbs_B):
        lsbs_B = generate_unique_lsb(count)

    # Construct full 64-bit numbers
    set_A = [f"0x00000000{lsb:08X}" for lsb in lsbs_A]
    set_B = [f"0xFFFFFFFF{lsb:08X}" for lsb in lsbs_B]

    # Write to files
    with open("set_A.txt", "w") as fA:
        fA.write("\n".join(set_A) + "\n")

    with open("set_B.txt", "w") as fB:
        fB.write("\n".join(set_B) + "\n")

    print(f"[INFO] Created set_A.txt and set_B.txt with {count} hex numbers each.")

if __name__ == "__main__":
    main()
