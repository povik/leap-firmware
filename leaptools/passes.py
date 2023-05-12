import itertools
import sys
from construct import hexdump

from .program import *
from .dsl import Builder

PASSES = {}
pass_counters = [1]

def program_pass(func):
    name = func.__name__

    def wrapper(*args, **kwargs):
        global pass_counters
        counter_str = "".join([f"{c}." for c in pass_counters])
        print(f"{counter_str} Running {name.upper()}", file=sys.stderr)
        pass_counters.append(1)
        try:
            ret = func(*args, **kwargs)
        finally:
            pass_counters.pop(-1)
            pass_counters[-1] += 1
        return ret
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    PASSES[name] = wrapper

    return wrapper

@program_pass
def special_reg(prg, regname):
    '''
    Mark that a given register is a special one and as such should
    not be abstracted away by deconstruction passes.
    '''
    prg.register_specials.add(Register.parse(regname))

@program_pass
def dump(prg):
    '''
    Dump the program and all its routines.
    '''
    prg.dump(sys.stderr)

@program_pass
def dump_py(prg):
    '''
    Dump a Python script emulating the current program. Routines
    are converted into Python functions, globals are converted
    into Python globals.

    Shortcomings:

     * Emulates LEAP floats with Python floats (the latter have
       additional precision).

     * Implements only a subset of the instruction set.

     * Assumes all globals to be floating-point, leading to
       errors in execution if a non-floating-point operand is
       sourced from a global.

     * Assumes separation of floating-point and fixed-point
       values so that one is never reinterpreted as the other
       in an operand.
    '''
    global global_cnt, inm_cnt
    labels = {}
    global_cnt = 0
    inm_cnt = 0
    def label(op):
        global global_cnt, inm_cnt
        if op in labels:
            return labels[op]
        elif type(op) is Global:
            l = f"global{global_cnt}"
            global_cnt += 1
        elif type(op) is Instruction:
            if op.out is not None:
                return label(op.out)
            l = f"inm{inm_cnt}"
            inm_cnt += 1
        else:
            raise NotImplementedError(type(op))

        labels[op] = l
        return l

    def conv(op, fpoint=False):
        if op is None:
            return "None"
        elif type(op) is Constant:
            if fpoint:
                return f"{op.float:.8E}"
            else:
                return f"{op.val:#x}"
        else:
            return label(op)

    all_globals = set()

    for routno, rout in enumerate(prg.routines):
        mentioned_globals = set()

        for i, inst in enumerate(rout.instr):
            if not rout.is_selected(inst):
                continue
            mentioned_globals.update([
                op for op in inst.ops + [inst.out] if type(op) is Global
            ])

        print(f"def rout{routno}():")
        global_line = ", ".join([label(g) for g in mentioned_globals])
        print(f"\tglobal {global_line}")
        all_globals |= mentioned_globals

        for i, inst in enumerate(rout.instr):
            if not rout.is_selected(inst):
                continue
            opcode = inst.opcode
            if opcode == Opcode.FMULTSUB:
                print(f"\t{label(inst)} = {conv(inst.op1, True)} - {conv(inst.op2, True)} * {conv(inst.op3, True)}")
            elif opcode == Opcode.FMULTACC:
                print(f"\t{label(inst)} = {conv(inst.op1, True)} + {conv(inst.op2, True)} * {conv(inst.op3, True)}")
            elif opcode == Opcode.FMULT:
                print(f"\t{label(inst)} = {conv(inst.op2, True)} * {conv(inst.op3, True)}")
            elif opcode == Opcode.FADD_DIV2:
                print(f"\t{label(inst)} = ({conv(inst.op1, True)} + {conv(inst.op2, True)}) / 2")
            elif opcode == Opcode.FSUB:
                print(f"\t{label(inst)} = {conv(inst.op2, True)} - {conv(inst.op1, True)}")
            elif opcode == Opcode.FMUX:
                print(f"\t{label(inst)} = {conv(inst.op2, True)} if ({conv(inst.op3, False)} & (1<<31)) else {conv(inst.op1, True)}")
            else:
                print(f"\t{label(inst)} = {opcode.name}({conv(inst.op1, False)}, {conv(inst.op2, False)}, {conv(inst.op3, False)})")
                #raise NotImplementedError(opcode)

    for g in all_globals:
        inits = [c for c in g.cases if type(c) is Constant]
        # TODO: decide if this should be float
        if not len(inits):
            continue

        print(f"{label(g)} = {inits[0].val:.8E}")

@program_pass
def graph(prg, routidx=None):
    '''
    Dump a graphviz representation of the program.
    '''

    f = sys.stdout
    global_drawn = set()

    print('digraph G {\nrankdir="LR";\nremincross=true;', file=f)

    def flt(val):
        return "{:.5E}".format(val)

    for i, rout in enumerate(prg.routines):
        if routidx is not None and i != routidx:
            continue
        print("subgraph cluster_%d {" % id(rout), file=f)
        for off, inst in enumerate(rout.instr):
            if not rout.is_selected(inst):
                continue
            idx = (rout.base if rout.base is not None else 0) + off
            print(f"\tinst{id(inst)}" + " [shape=record label=\"{{<op1>OP1|<op2>OP2|<op3>OP3}|{" + \
                  f"{inst.opcode.name}|{idx:x}" + "}|<res>OUT}\"];", file=f)
            for i, op in enumerate(inst.ops):
                is_float = inst.is_float_op(i)
                if type(op) is BadOperand or op is None:
                    continue
                elif type(op) is Instruction:
                    print(f"\tinst{id(op)}:res -> inst{id(inst)}:op{i + 1};")
                elif type(op) is Constant:
                    print(f"\tinst{id(inst)}const{id(op)} [label=\"{flt(op.float) if is_float else hex(op.val)}\" shape=cds];", file=f)
                    print(f"\tinst{id(inst)}const{id(op)} -> inst{id(inst)}:op{i + 1};")
                elif type(op) is Uninitialized:
                    print(f"\tuninit{id(op)} [label=\"uninitialized\" color=gray shape=cds];", file=f)
                    print(f"\tuninit{id(op)} -> inst{id(inst)}:op{i + 1};")
                elif type(op) is Register:
                    print(f"\treg_{op} [shape=Mdiamond label=\"{op}\"];", file=f)
                    print(f"\treg_{op} -> inst{id(inst)}:op{i + 1};")
                elif type(op) is Global:
                    print(f"\tglobal{id(op)} -> inst{id(inst)}:op{i + 1};")
                    if op in global_drawn:
                        continue
                    global_drawn.add(op)

                    print(f"\tglobal{id(op)} [shape=diamond label=\"\"];", file=f)
                    for case in op.cases:
                        if type(case) is Instruction:
                            print(f"\tinst{id(case)}:res -> global{id(op)};")
                        elif type(case) is Constant:
                            print(f"\tglobal{id(op)}const{id(case)} [label=\"{flt(case.float) if is_float else hex(case.val)}\" shape=cds];", file=f)
                            print(f"\tglobal{id(op)}const{id(case)} -> global{id(op)};")
                        elif type(case) is Uninitialized:
                            print(f"\tuninit{id(case)} [label=\"uninitialized\" color=gray shape=cds];", file=f)
                            print(f"\tuninit{id(case)} -> global{id(op)};")
                        else:
                            raise NotImplementedError(op)
                else:
                    raise NotImplementedError(op)
        print("}", file=f)
    print("}", file=f)

@program_pass
def deconstruct_regrings(prg):
    '''
    Replace register references with register ring references
    where applicable.
    '''

    for rout in prg.routines:
        written = set()

        for inst in rout.instr:
            for i, regop in enumerate(inst.ops):
                if type(regop) is not Register or \
                        regop in prg.register_specials:
                    continue
                for ring in rout.rings:
                    if regop in ring:
                        if ring in written:
                            raise ValueError(f"writes-after-reads on the same register ring from one routine are not supported")
                        inst.ops[i] = RingOperand(ring, ring.decode_offset(regop))
            for ring in rout.rings:
                if type(inst.out) is not Register or \
                        inst.out in prg.register_specials:
                    continue
                if inst.out in ring:
                    inst.out = RingOperand(ring, ring.decode_offset(inst.out))
                    written.add(ring)

@program_pass
def deconstruct_simpleregs(prg):
    '''
    Walk through the program and rewrite instruction operands
    so that they point to earlier instructions instead of any
    registers holding the results. That is, abstract away
    the registers and revert the process of register allocation.
    '''

    final_setters = dict()

    for reg, val in prg.register_inits.items():
        final_setters[reg] = [Constant(val)]

    for rout in prg.routines:
        rout_final = dict()
        for inst in rout.instr:
            if inst.out is None:
                continue
            rout_final[inst.out] = inst
        for k, v in rout_final.items():
            if k not in final_setters:
                final_setters[k] = [Uninitialized()]
            final_setters[k].append(v)

    final_setters = {
        k: Global(*v) if len(v) > 1 else v[0] \
        for k, v in final_setters.items()
    }

    for rout in prg.routines:
        state = {}
        for inst in rout.instr:
            for i, regop in enumerate(inst.ops):
                if type(regop) is not Register or \
                        regop in prg.register_specials:
                    continue
                elif regop in state:
                    newop = state[regop]
                elif regop in final_setters:
                    newop = final_setters[regop]
                else:
                    final_setters[regop] = newop = Uninitialized()
                inst.ops[i] = newop
            state[inst.out] = inst

@program_pass
def add_regring(prg, routidx, base, depth, width):
    depth = int(depth)
    base_reg = Register.parse(base)
    rout = prg.routines[int(routidx)]
    rout.rings.append(RegisterRing(depth, width,
                            bank=base_reg.bank,
                            base=base_reg.addr))

@program_pass
def deconstruct(prg):
    deconstruct_regrings(prg)
    deconstruct_simpleregs(prg)

@program_pass
def select(prg, routidx, instrpos):
    '''
    Select a subset of a routine by pointing to an instruction.
    The instruction and all its prerequisite instructions within
    the routine will be selected. Follow-up "dump" passes will be
    restricted to this selected subset. This only works on a
    deconstructed program with abstract operands.

    Usage:

        select ROUTINE_INDEX INSTRUCTION_INDEX
    '''

    rout = prg.routines[routidx]
    visited = set()
    visitq = [rout.instr[instrpos]]
    while visitq:
        nex = visitq.pop()
        if nex in visited:
            continue
        if type(nex) is Instruction:
            for op in nex.ops:
                if op is None or type(op) is not Register:
                    continue
                if op in prg.register_specials:
                    continue
                print(f"WARNING: Non-deconstructed instruction: {nex}")
                break
        visitq += nex.deps()
        visited.add(nex)    
    rout.selected = visited

@program_pass
def select_none(prg, routidx=None):
    prg.routines[routidx].selected = set()

@program_pass
def unselect(prg, routidx=None):
    '''
    Clear any prior selections.

    Usage:

        unselect [ROUTINE_INDEX]
    '''

    if routidx is not None:
        prg.routines[routidx].selected = None
    else:
        for rout in prg.routines:
            rout.selected = None

@program_pass
def clear_outs(prg):
    '''
    Clear any output register allocations of instructions, instead
    put in Globals where applicable.
    '''
    global_writers = dict()
    for rout in prg.routines:
        for inst in rout.instr:
            for op in inst.ops:
                if type(op) is not Global:
                    continue
                for case in op.cases:
                    if type(case) is Instruction:
                        global_writers[case] = op

    for rout in prg.routines:
        for inst in rout.instr:
            if type(inst.out) is RingOperand:
                continue
            inst.out = global_writers.get(inst, None)

@program_pass
def wipe_inits(prg):
    '''
    Wipe any register initializations.
    '''
    prg.register_inits = {}

def get_placement_constraints(prg, rout):
    instr = set([inst for inst in rout.instr if inst is not None])
    sideeffect = []
    constraints = []

    for inst in rout.instr:
        if inst is None:
            continue
        for op in inst.ops:
            if op in instr:
                spacing = 0
                if op.opcode in [Opcode.FMULTSUB, Opcode.FMULTACC,
                                 Opcode.FMULTACC_NEG]:
                    spacing = 1
                constraints.append((inst, op, spacing, 1, "result-to-operand"))
            if type(op) is Global:
                for case in op.cases:
                    if case in instr:
                        # instructions updating a global can only go *after*
                        # an instruction sourcing an operand from said global
                        constraints.append((case, inst, -1, 0, "global update-after-use"))
        if inst.has_side_effects:
            # instructions with side effects must not be reordered
            if len(sideeffect):
                constraints.append((inst, sideeffect[-1], 0, 0, "side effect ordering"))
            sideeffect.append(inst)

    return constraints

@program_pass
def check_placement(prg, routidx):
    '''
    Check routine instruction placement satisfies constraints.
    '''
    rout = prg.routines[routidx]
    constraints = get_placement_constraints(prg, rout)

    for constr in constraints:
        endp, base, offset, cost, cause = constr
        base_idx = rout.instr.index(base)
        endp_idx = rout.instr.index(endp)

        if endp_idx <= base_idx + offset:
            print("Constraint violation:", file=sys.stderr)
            print("", file=sys.stderr)
            print(f"  {base_idx:2x}: {base}", file=sys.stderr)
            print(f"  {endp_idx:2x}: {endp}", file=sys.stderr)
            print("", file=sys.stderr)
            print(f"violate a constraint: {cause}", file=sys.stderr)

@program_pass
def place_routine(prg, routidx):
    '''
    Order instructions to satisfy constraints (single routine).
    '''
    rout = prg.routines[routidx]

    instr = set(rout.instr)
    constraints = get_placement_constraints(prg, rout)

    inst_blockers = dict()
    blocking = dict()
    for inst in rout.instr:
        inst_blockers[inst] = []
        blocking[inst] = []

    for const in constraints:
        endp, base, offset, cost, _ = const
        inst_blockers[endp].append(const)
        blocking[base].append(const)

    ready = []
    for inst in rout.instr:
        if not len(inst_blockers[inst]):
            ready.append(inst)

    placed = []
    nplaced = 0
    while nplaced < len(instr):
        if len(ready):
            placed.append(ready.pop())
            nplaced += 1
        else:
            placed.append(None)

        for back in range(min(2, len(placed))):
            ioi = placed[-1 - back]
            if ioi is None:
                continue
            for const in blocking[ioi]:
                endp, base, offset, cost, _ = const
                if offset > back or not len(inst_blockers[endp]):
                    continue
                if const in inst_blockers[endp]:
                    inst_blockers[endp].remove(const)
                if not len(inst_blockers[endp]):
                    ready.append(endp)

    # TODO: optimize the initial placement further
    rout.instr = placed

    check_placement(prg, routidx)

@program_pass
def place(prg):
    '''
    Order instructions to satisfy constraints (all of program).
    '''
    for i, _ in enumerate(prg.routines):
        place_routine(prg, i)

@program_pass
def regalloc_intermediate(prg, routidx=None):
    '''
    Allocates instructions' register outputs.

    BUG: instruction can either update a global or have
         its result available as an intermediate, not both!
    '''

    if routidx is None:
        for i, _ in enumerate(prg.routines):
            regalloc_intermediate(prg, i)
        return

    rout = prg.routines[routidx]
    instr_of_interest = set()
    edges = set()

    for inst in rout.instr:
        if inst is None:
            continue

        inst_deps = [
            op for op in inst.ops if type(op) in [Instruction, Global]
        ]

        for inst in inst_deps:
            instr_of_interest.add(inst)

        for comb in itertools.combinations(inst_deps, 2):
            edges.add(frozenset(comb))

    # SAT variable: is output of instruction X stored in bank Y?
    bank_var = {
        inst: (i+1, i+2, i+3)
        for inst, i in zip(instr_of_interest,
                           range(0, 3 * len(instr_of_interest), 3))
    }

    clauses = []

    for _, bv in bank_var.items():
        clauses.append(list(bv))

    for edge in edges:
        a, b = edge
        for bank in range(3):
            clauses.append([-bank_var[a][bank], -bank_var[b][bank]])

    import pycosat
    sol = pycosat.solve(clauses)
    if type(sol) is not list:
        raise RuntimeError(f"SAT solver couldn't solve for bank assignment: code {sol}")

    allocators = [
        RegAllocator(bank, prg.register_allocated)
        for bank in [1, 2, 3]
    ]

    for inst in instr_of_interest:
        indices = bank_var[inst]
        bank = [sol[i - 1] > 0 for i in indices].index(True)
        reg = allocators[bank]()
        prg.register_allocated.add(reg)
        inst.out = reg
        if type(inst) is Global:
            for case in inst.cases:
                if type(case) is Instruction:
                    case.out = reg
                elif type(case) is Constant:
                    prg.register_inits[reg] = case.val

@program_pass
def regalloc_const(prg, routidx=None):
    '''
    Allocate registers for constants.
    '''
    if routidx is None:
        for i, _ in enumerate(prg.routines):
            regalloc_const(prg, i)
        return

    rout = prg.routines[routidx]

    allocators = [
        RegAllocator(bank, prg.register_allocated)
        for bank in [1, 2, 3]
    ]

    for inst in rout.instr:
        if inst is None:
            continue

        free_banks = [1, 2, 3]
        for i, op in enumerate(inst.ops):
            if type(op) is not Register:
                continue
            if op.bank in free_banks:
                free_banks.remove(op.bank)

        for i, op in enumerate(inst.ops):
            if type(op) is not Constant:
                continue
            bank = free_banks.pop()
            reg = allocators[bank - 1]()
            prg.register_inits[reg] = op.val
            inst.ops[i] = reg
            prg.register_allocated.add(reg)

@program_pass
def set_nops(prg):
    '''
    Put in some designed NOP instruction into empty instruction
    positions within routines.
    '''
    nnops = 0
    for rout in prg.routines:
        for i, inst in enumerate(rout.instr):
            if inst is None:
                # until we figure out something better, we insert a dummy AND op
                rout.instr[i] = Instruction(Opcode.AND)
                nnops += 1
    print(f"Set {nnops} NOPs.   ", file=sys.stderr)

@program_pass
def propagate_outs(prg):
    '''
    Rewrite instruction operands to replace instruction references
    with register references. That is done according to the assigned
    output registers of referenced instructions.
    '''
    for rout in prg.routines:
        for inst in rout.instr:
            if inst is None:
                continue
            for i in range(len(inst.ops)):
                if type(inst.ops[i]) not in [Instruction, Global]:
                    continue
                if inst.ops[i].out is None:
                    continue
                inst.ops[i] = inst.ops[i].out

@program_pass
def load_dsl(prg, fname):
    '''
    Build an (abstract) program from a DSL representation in a Python
    script (expects a filename).
    '''
    b = Builder(prg)

    with open(fname) as f:
        compiled = compile(f.read(), fname, "exec")
        exec(compiled, dict(), {'b': b, 'Global': Global})

    print(f"Built {b.nroutines} routines containing {b.ninstr} instructions.",
          file=sys.stderr)

@program_pass
def arrange_routines(prg):
    '''
    Arrange routines in instruction memory (assign them bases).
    '''
    base = 0
    for r in prg.routines:
        r.base = base
        base += len(r.instr) + 1

@program_pass
def image(prg):
    '''
    Build a program image, output it on standard output.
    '''
    img = prg.build_image()
    print(f"Writing image with {len(img.sections)} sections:", file=sys.stderr)
    for sect in img.sections:
        print(f"    {sect.type.name:6s} base {sect.load_base:x} size {sect.size:x} flags {sect.flags}",
              file=sys.stderr)
    img.write(sys.stdout.buffer)

@program_pass
def image_inline(prg):
    '''
    Build a program image, return it (to be embedded in other passes).
    '''
    img = prg.build_image()
    print(f"Writing image with {len(img.sections)} sections:", file=sys.stderr)
    for sect in img.sections:
        print(f"    {sect.type.name:6s} base {sect.load_base:x} size {sect.size:x} flags {sect.flags}",
              file=sys.stderr)
    return bytes(img)

@program_pass
def image_hexdump(prg):
    '''
    Build a program image, print its hexdump.
    '''
    img = prg.build_image()
    print(f"Writing image with {len(img.sections)} sections:", file=sys.stderr)
    for sect in img.sections:
        print(f"    {sect.type.name:6s} base {sect.load_base:x} size {sect.size:x} flags {sect.flags}",
              file=sys.stderr)
    print(hexdump(bytes(img), linesize=16))

@program_pass
def compile_dsl(prg=None, fname=""):
    '''
    Do end-to-end compilation of a program from DSL to image.
    '''
    if prg is None:
        prg = Program()
    load_dsl(prg, fname)
    place(prg)
    regalloc_intermediate(prg)
    propagate_outs(prg)
    regalloc_const(prg)
    set_nops(prg)
    arrange_routines(prg)
    dump(prg)
    return image_inline(prg)

@program_pass
def asm(prg=None, fname=""):
    '''
    Do roughly the inverse of 'dump'.
    '''

    with open(fname) as f:
        for line in f:
            line = line.strip()
            if line.startswith("# Routine"):
                prg.routines.append(Routine())
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                line = line.split(":")[1].strip()
            opcode, trail = line.split(" ", 1)
            ops = trail.split(",", 4)
            prg.routines[-1].instr.append(Instruction(
                Opcode.__members__[opcode],
                *map(Register.parse, ops)
            ))
