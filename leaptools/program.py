import struct

from .types import *
from .image import Image, Section, SectionFlags

class Operand:
    pass

class BadOperand(Operand):
    def __init__(self):
        pass

    def __str__(self):
        return "??"

    def __hash__(self):
        return id(type(self))

    def __eq__(self, other):
        return type(other) is type(self)

class Uninitialized(Operand):
    def __init__(self):
        pass

class Constant(Operand):
    def __init__(self, val):
        self.val = val

    @classmethod
    def from_float(self, val):
        byts = struct.pack('>f', val)
        return Constant(int.from_bytes(byts, byteorder="big"))

    @property
    def float(self):
        return struct.unpack('>f', self.val.to_bytes(4, byteorder="big"))[0]

    def deps(self):
        return []

    def operand_str(self):
        return f"={self.val:08x}"

class Global(Operand):
    def __init__(self, *cases, name=None, init=None):
        self.cases = list(cases)
        if init is not None:
            self.cases.append(Constant(init))
        self.out = None

    def deps(self):
        return self.cases

    def operand_str(self):
        return f"one of {'/'.join([op.operand_str() for op in self.cases])}"

class Register(Operand):
    @classmethod
    def parse(self, name):
        name = name.strip()
        if name == "--":
            return None
        if len(name) < 2 or name[0] not in "abc":
            raise ValueError(f"bad register name: {name!r}")
        return Register(
            " abc".index(name[0]),
            int(name[1:], 16)
        )

    def __init__(self, bank, addr):
        self.bank, self.addr = bank, addr

    def __str__(self):
        return f"{' abc'[self.bank]}{self.addr:02x}"

    def __hash__(self):
        return hash((self.bank, self.addr))

    def __eq__(self, other):
        return (self.bank, self.addr) == (other.bank, other.addr)

    def deps(self):
        return []

    def operand_str(self):
        return str(self)

class Instruction(Operand):
    def __init__(self, opcode, *ops):
        self.opcode = Opcode(opcode)
        self.out = ops[0] if len(ops) else None
        self.ops = (list(ops) + [None, None, None, None])[1:4]

    @classmethod
    def decode(self, *pieces):
        fields = GeneralInstr(pieces[0])
        opspecs = pieces[1:]
        opbanks = [fields.OP1BANK, fields.OP2BANK, fields.OP3BANK]

        try:
            opcode = fields.OPCODE1 | (fields.OPCODE2 << 8)
            opcode_enum = Opcode(opcode)
        except ValueError:
            raise ValueError(f'instruction decode: unknown opcode {opcode:#x}')

        return Instruction(
            opcode_enum,
            Register(fields.OUTBANK, fields.OUTADDR) \
                if fields.OUTBANK != 0 else None,
            *[self._resolve_op(b, opspecs) for b \
                in opbanks]
        )

    @classmethod
    def _resolve_op(self, bank, opspecs):
        if bank == 0:
            return None # TODO: BadOperand?
        return Register(bank, opspecs[bank - 1])

    def is_float_op(self, idx):
        # TODO
        return self.opcode.name.startswith("F") 

    def encode(self):
        for op in self.ops:
            assert op is None or type(op) is Register

        opspecs = [None, None, None]
        opbanks = [0, 0, 0]
        for i, op in enumerate(self.ops):
            if op is None:
                continue
            assert opspecs[op.bank - 1] is None \
                or opspecs[op.bank - 1] == op.addr
            opspecs[op.bank - 1] = op.addr
            opbanks[i] = op.bank

        fields = GeneralInstr(0,
            OPCODE1=self.opcode, OPCODE2=self.opcode >> 8,
            OP1BANK=opbanks[0], OP2BANK=opbanks[1], OP3BANK=opbanks[2],
            **({'OUTBANK': self.out.bank, 'OUTADDR': self.out.addr}
               if self.out is not None else {})
        )

        return (int(fields),) + tuple(s or 0 for s in opspecs)

    @property
    def op1(self):
        return self.ops[0]

    @property
    def op2(self):
        return self.ops[1]

    @property
    def op3(self):
        return self.ops[2]

    def deps(self):
        return [op for op in self.ops if op is not None]

    def operand_str(self):
        return f"<instr result: {self.opcode.name} @ {id(self)}>"

    @property
    def has_side_effects(self):
        return self.opcode in range(0xa0, 0xc0)

    def __str__(self):
        operand_list = ", ".join([
            op.operand_str() if op is not None else "--"
            for op in [self.out] + self.ops
        ])
        return f"{self.opcode.name} {operand_list}"

class Routine:
    def __init__(self, base=None, instr=None, waitfull_ports=[], waitempty_ports=[]):
        self.instr = instr or []
        self.base = base
        self.selected = None
        self.waitfull_ports = waitfull_ports
        self.waitempty_ports = waitempty_ports

    def __iadd__(self, v):
        assert type(v) in [Instruction, list, tuple]
        if type(v) is Instruction:
            v = [v]
        self.instr += v
        return self

    def is_selected(self, inst):
        return (inst in self.selected) if self.selected is not None else True

    def dump(self, f):
        for off, inst in enumerate(self.instr):
            if not self.is_selected(inst):
                continue
            if self.base is not None:
                print(f"{self.base + off:03x}: {str(inst)}", file=f)
            else:   
                print(f"+{off:02x}: {str(inst)}", file=f)

class Program:
    def __init__(self):
        self.register_inits = {}
        self.register_specials = set()
        self.register_allocated = set()
        self.routines = []

    @classmethod
    def from_image(self, img):
        prg = Program()

        for routine_span in img.routines:
            instr_parts = img[
                Section.INST0:Section.INST3 + 1,
                routine_span
            ]
            prg.routines.append(Routine(
                routine_span.start,
                [Instruction.decode(*pieces)
                 for pieces in zip(*instr_parts)]
            ))

        for typ, span in img.section_spans(range(Section.STATE1,
                                                 Section.STATE3 + 1)):
            bank = typ - Section.STATE0
            for addr_delta, val in enumerate(img[typ,span]):
                reg = Register(bank, span.start + addr_delta)
                prg.register_inits[reg] = val

        for rout in prg.routines:
            waitbase = rout.base << 16
            rout.waitfull_ports = img[Section.WAITFULL_LIST,waitbase:]
            rout.waitempty_ports = img[Section.WAITEMPTY_LIST,waitbase:]

        return prg

    def build_image(self):
        img = Image()

        for secttype in range(Section.STATE1, Section.STATE3 + 1):
            inits = { k.addr: v for k, v in self.register_inits.items() \
                      if k.bank == secttype - Section.STATE0 }
            if not len(inits):
                continue
            base = min(inits.keys())
            end = max(inits.keys()) + 1
            img.reserve(secttype, range(base, end), 0)
            for addr, val in inits.items():
                img[secttype, addr] = val

        for rout in self.routines:
            assert rout.base is not None
            span = range(rout.base, rout.base + len(rout.instr))
            img.reserve(Section.INST0, span, SectionFlags.ROUTINE)
            img.reserve(Section.INST1, span, SectionFlags.ROUTINE)
            img.reserve(Section.INST2, span, SectionFlags.ROUTINE)
            img.reserve(Section.INST3, span, SectionFlags.ROUTINE)

            for off, inst in enumerate(rout.instr):
                idx = rout.base + off
                img[Section.INST0:Section.INST3 + 1, idx] = inst.encode()

            waitbase = rout.base << 16

            if (nports := len(rout.waitempty_ports)):
                img.reserve(Section.WAITEMPTY_LIST, range(waitbase, waitbase + nports))
                for i, port in enumerate(sorted(rout.waitempty_ports)):
                    img[Section.WAITEMPTY_LIST,waitbase + i] = port

            if (nports := len(rout.waitfull_ports)):
                img.reserve(Section.WAITFULL_LIST, range(waitbase, waitbase + nports))
                for i, port in enumerate(sorted(rout.waitfull_ports)):
                    img[Section.WAITFULL_LIST,waitbase + i] = port

        return img

    def dump(self, f):
        for no, r in enumerate(self.routines):
            print(f"     # Routine {no}", file=f)
            r.dump(f)

class RegAllocator:
    def __init__(self, bank, mask):
        self.bank = bank
        self.next_free = 0
        self.mask = mask

    def __call__(self):
        reg = Register(self.bank, self.next_free)
        while reg in self.mask:
            reg = Register(reg.bank, reg.addr + 1)
        self.next_free = reg.addr + 1
        return reg
