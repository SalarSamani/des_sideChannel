import chipwhisperer as cw
import time

scope = None
target = None

def init():
    global scope, target
    try:
        scope = cw.scope(sn="442031204c5032433130333234313031")
        target = cw.target(scope)
        scope.default_setup()
        print("[INFO] Found ChipWhisperer 😍")
    except Exception as e:
        print("[INFO] ChipWhisperer is missing 😢")
        print(e)
        exit(-1)

def reset():
    scope.io.nrst = 'low'
    time.sleep(0.05)
    scope.io.nrst = 'high_z'
    time.sleep(0.05)

def run_task0():
    tests = [
        ("4142434445464748", "ef770c97ad062c75"),
        ("4141414142424242", "94707c838caadfa7"),
        ("4242424243434343", "5f1b46e2852eadf7")
    ]
    for pt_hex, expected_ct_hex in tests:
        pt = bytes.fromhex(pt_hex)
        target.simpleserial_write('d', pt)
        ct = target.simpleserial_read('r', 8)
        print(f"Plaintext:  {pt_hex}")
        print(f"Received:   {ct.hex()}")
        print(f"Expected:   {expected_ct_hex}")
        print("Match ✅" if ct.hex() == expected_ct_hex else "Mismatch ❌")
        print("-" * 40)

if __name__ == '__main__':
    init()
    reset()
    run_task0()
    scope.dis()
    target.dis()
