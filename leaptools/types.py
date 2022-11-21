from enum import IntEnum

class BitFieldsValue:
    def __init__(self, val, **kwargs):
        l = []
        self._fieldnames = l
        self._fieldmask = 0
        for cls in self.__class__.mro():
            l += [k for k in cls.__dict__.keys() \
                  if not k.startswith("_")]
        for field in l:
            top, bot = getattr(self.__class__, field)
            self._fieldmask |= (-1 << (top + 1)) ^ (-1 << bot)

        self._val = val
        for k, v in kwargs.items():
            top, bot = getattr(self.__class__, k)
            mask = (1 << (top - bot + 1)) - 1
            self._val |= (v & mask) << bot

    def __getattribute__(self, attrname):
        if attrname.startswith("_"):
            return object.__getattribute__(self, attrname)
        top, bot = getattr(self.__class__, attrname)
        mask = (1 << (top - bot + 1)) - 1
        return (self._val >> bot) & mask

    def __str__(self):
        return ", ".join([f"{n}={getattr(self, n):x}" for n \
                          in self._fieldnames])

    def __int__(self):
        return self._val

class GeneralInstr(BitFieldsValue):
    OUTADDR = 31, 19

    OPCODE2 = 18, 17
    OUTBANK = 15, 14
    OP3BANK = 13, 12
    OP2BANK = 11, 10
    OP1BANK = 9,   8
    OPCODE1 = 7,   0

class Opcode(IntEnum):
    FRACMULT = 0x00

    ADD  = 0x80
    ADD_DIV2 = 0x81
    SUB  = 0x82
    SUB_DIV2 = 0x83
    ADD_UNS  = 0x84
    ABS  = 0x85
    MAX  = 0x86
    MIN  = 0x87
    MUX  = 0x88
    AND  = 0x89
    OR   = 0x8a
    XOR  = 0x8b
    CLR  = 0x8c
    ZERO = 0x8d
    ADD2 = 0x8e
    ADD3 = 0x8f
    ZERO2 = 0x90
    ZERO3 = 0x91
    ZERO4 = 0x92
    CLAMP = 0x93
    ROT  = 0x94
    PDM1 = 0x95 # one-in-4 decimation
    PDM2 = 0x96
    PDM3 = 0x97 # one-in-3 decimation
    PDM4 = 0x98
    PDM5 = 0x99 # one-in-5 decimation
    PDM6 = 0x9a
    CMP  = 0x9b
    CMP2 = 0x9c
    EQ   = 0x9d
    ADD4 = 0x9e
    SUB2 = 0x9f

    TAKE   = 0xa0
    TAKEC  = 0xa1
    PEEK   = 0xa2
    PUT    = 0xa4
    PUTC   = 0xa5
    UPDATE = 0xa6

    UNK_bf = 0xbf

    FCMP    = 0xe0
    FCMP2   = 0xe1
    FMUX    = 0xe5
    F32_FMT = 0xed

    FADD      = 0x1c0
    FADD_ABS  = 0x1c1
    FADD_DIV2 = 0x1c2
    FSUB      = 0x1c3
    FSUB_ABS  = 0x1c4
    FSUB_DIV2 = 0x1c5

    FMULT        = 0x1c6
    FMULTACC     = 0x1c7
    FMULT_NEG    = 0x1d6
    FMULTACC_NEG = 0x1d7
    FMULTSUB     = 0x1d8

    MULT31 = 0x2e0
    # ...
    MULT0  = 0x2ff
