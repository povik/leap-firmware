import argparse
import random
import math
import sys
import os

from leaptools.types import *

true_stdout = sys.stdout
sys.stdout = sys.stderr

def batch_execute(inp, flags):
    from leaptools.proxysetup import u, iface, lp, UartChecksumError
    with u.heap.guarded_malloc(4 * 1024 * 1024) as scratch:
        scratch0 = scratch
        scratch1 = scratch + 2 * 1024 * 1024

        iface.writemem(scratch0, inp)
        ncases = len(inp) // LEAPExecutionInfo.sizeof()
        lp.run_leap_testcases(ncases, scratch0, scratch1, int(flags))
        for _ in range(3):
            try:
                return iface.readmem(scratch1, ncases * LEAPContext.sizeof())
            except UartChecksumError:
                pass
            print("Repeat readmem!", file=sys.stderr)

def randomize_banks(testcluster):
    from leaptools.proxysetup import testcluster
    r = testcluster.regs
    testcluster.load_context(Container(
        bank0=[random.randint(0, 1<<32 - 1) for _ in range(len(r.STATE0.range.ranges[0]))],
        bank1=[random.randint(0, 1<<32 - 1) for _ in range(len(r.STATE1.range.ranges[0]))],
        bank2=[random.randint(0, 1<<32 - 1) for _ in range(len(r.STATE2.range.ranges[0]))],
        bank3=[random.randint(0, 1<<32 - 1) for _ in range(len(r.STATE3.range.ranges[0]))],
    ))

tally = 0
boring = 0
flaky = 0
def flush_counters():
    global tally, boring, flaky
    print(f"Out of the {tally} testcases ran:", file=sys.stderr)
    if flaky:
        print(f"\t{flaky:8d} (one in 2**{math.log2(tally/flaky):2.2f}) were flaky (not a " + \
              "function of cropped state).", file=sys.stderr)
    if boring:
        print(f"\t{boring:8d} (one in 2**{math.log2(tally/boring):2.2f}) were boring.",
              file=sys.stderr)
    tally, boring, flaky = 0, 0, 0

def batch_run_n_check(inp):
    global tally, boring, flaky
    from leaptools.proxysetup import u, testcluster

    # Execute once w/ zeroed-out banks (apart from the cropped region
    # which we set according to the testcases)
    res1 = batch_execute(inp, LEAPTestrunnerFlags.CLEAN_SLATE)

    # Now run again but initialize the context outside the cropped region
    # randomly
    randomize_banks(testcluster)
    res2 = batch_execute(inp, 0)

    # Again but exchange randomness
    randomize_banks(testcluster)
    res3 = batch_execute(inp, 0)

    # We are interested in testcases which
    #  (1) modify the context (keeping the occurence of those that don't below 1%)
    #  (2) are independent of the state beyond the cropped region
    pieces = []
    ngood = 0
    infolen = LEAPExecutionInfo.sizeof()
    ctxlen = LEAPContext.sizeof()
    for i in range(len(inp) // LEAPExecutionInfo.sizeof()):
        tally += 1
        tc = inp[i * infolen:(i + 1) * infolen]
        r1 = res1[i * ctxlen:(i + 1) * ctxlen]
        r2 = res2[i * ctxlen:(i + 1) * ctxlen]
        r3 = res3[i * ctxlen:(i + 1) * ctxlen]

        if r1 != r2 or r1 != r3:
            print(f"Flaky: {int.from_bytes(tc[0x400:0x404], byteorder='little'):#x}")
            flaky += 1
            continue

        if r1 == tc[:ctxlen]:
            print(f"Boring: {int.from_bytes(tc[0x400:0x404], byteorder='little'):#x}")
            boring += 1
            if random.randint(0, 99) != 0:
                continue

        # This one is good to go!
        pieces += [tc, r1]
        ngood += 1

    return ngood, b"".join(pieces)

def flat_generate(number):
    return os.urandom(number * LEAPExecutionInfo.sizeof())

def sidebanks0_generate(number):
    infolen = LEAPExecutionInfo.sizeof()
    ret = bytearray(infolen * number)
    retview = memoryview(ret)
    for i in range(number):
        sub = retview[i * infolen:(i + 1) * infolen]
        sub[0:0x100] = os.urandom(0x100)
        sub[0x100:0x104] = os.urandom(0x4)
        sub[0x200:0x204] = os.urandom(0x4)
        sub[0x300:0x304] = os.urandom(0x4)
        sub[0x400:0x404] = os.urandom(0x4)
    return ret

def tuned_generate_instruction():
    while True:
        inst = (random.randint(0, 1) << 17) | (0b01111001 << 8) \
                | random.randint(0, 255)
        if (inst & 0xff) not in range(0xa0, 0xc0) \
            and (inst & 0xff) not in range(0xd0, 0xd6):
            break
    return inst.to_bytes(4, byteorder='little')

def tuned_generate(number):
    infolen = LEAPExecutionInfo.sizeof()
    ret = bytearray(infolen * number)
    retview = memoryview(ret)
    for i in range(number):
        sub = retview[i * infolen:(i + 1) * infolen]
        sub[0x100:0x104] = os.urandom(0x4)
        sub[0x200:0x204] = os.urandom(0x4)
        sub[0x300:0x304] = os.urandom(0x4)
        sub[0x400:0x404] = tuned_generate_instruction()
    return ret

def crux1_sample_instruction():
    while True:
        inst = int.from_bytes(os.urandom(4), byteorder='little')
        inst &= 0x2ffff | 0x1f80000
        fields = GeneralInstr(inst)
        if fields.OPCODE1 in range(0xa0, 0xc0) \
                or fields.OPCODE1 in range(0xd0, 0xd6):
            continue
        op_banks = set([fields.OP1BANK, fields.OP2BANK, fields.OP3BANK])
        if 0 in op_banks or fields.OUTBANK == 0:
            continue
        if len(op_banks) < 3 and random.randint(0, 19) != 0:
            continue
        return inst

def crux1_generate(number):
    infolen = LEAPExecutionInfo.sizeof()
    ret = bytearray(infolen * number)
    retview = memoryview(ret)
    for i in range(number):
        tc = retview[i * infolen:(i + 1) * infolen]
        tc[0x100:0x400] = os.urandom(0x300) # banks 1 to 3
        inst = crux1_sample_instruction() 
        tc[0x400:0x404] = inst.to_bytes(4, byteorder='little')
        tc[0x404] = random.randint(0, 0x3f)
        tc[0x408] = random.randint(0, 0x3f)
        tc[0x40c] = random.randint(0, 0x3f)
    return ret

def crux1_narrow_generate(number):
    infolen = LEAPExecutionInfo.sizeof()
    ret = bytearray(infolen * number)
    retview = memoryview(ret)
    for i in range(number):
        tc = retview[i * infolen:(i + 1) * infolen]
        tc[0x100:0x104] = os.urandom(0x4)
        tc[0x200:0x204] = os.urandom(0x4)
        tc[0x300:0x304] = os.urandom(0x4)
        inst = crux1_sample_instruction() & ~0x1f80000
        tc[0x400:0x404] = inst.to_bytes(4, byteorder='little')
    return ret

def generator(name):
    return {
        'flat': flat_generate,
        'crux1': crux1_generate,
        'crux1_narrow': crux1_narrow_generate,
    }[name]

def run(args):
    from leaptools.proxysetup import testcluster
    testcluster.reset()
    testcluster.enable()
    ncollected = 0
    tclen = LEAPExecutionInfo.sizeof() + LEAPContext.sizeof()
    while ncollected < args.number:
        n, data = batch_run_n_check(args.generator(1024))
        n = min(n, args.number - ncollected)
        true_stdout.buffer.write(data[:tclen * n])
        ncollected += n
    flush_counters()

def main():
    parser = argparse.ArgumentParser(description='Generate or process LEAP ISA testcases')
    parser.add_argument('-N', '--number', type=int, default=1000,
                        help='target number to generate')
    parser.add_argument('-g', '--generator', type=generator, default=flat_generate,
                        help='the testcase generator selected')
    parser.add_argument('-s', '--shuffle', action='store_true',
                        help='read in testcases, shuffle them, and write them out')
    parser.add_argument('-c', '--check', action='store_true',
                        help='read in testcases and check we can reproduce them')
    args = parser.parse_args()

    if args.shuffle:
        cases = []
        tc_size = LEAPExecutionInfo.sizeof() + LEAPContext.sizeof()
        while len(piece := sys.stdin.buffer.read(tc_size)):
            cases.append(piece)
        random.shuffle(cases)
        for tc in cases:
            true_stdout.buffer.write(tc)
    elif args.check:
        from leaptools.proxysetup import p, testcluster
        testcluster.reset()
        testcluster.enable()

        f = sys.stdin.buffer
        while True:
            try:
                info = LEAPExecutionInfo.parse_stream(f)
            except StreamError:
                break
            observed = LEAPContext.parse_stream(f)
            observed2 = LEAPContext.parse(batch_execute(LEAPExecutionInfo.build(info), LEAPTestrunnerFlags.CLEAN_SLATE))
    else:
        run(args)

if __name__ == '__main__':
    main()
