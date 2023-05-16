import sys
import bisect
from enum import IntEnum
from construct import *

class LEAPFROGSectionType(IntEnum):
    STATE0 = 0x10000
    STATE1 = 0x10001
    STATE2 = 0x10002
    STATE3 = 0x10003

    INST0 = 0x20000
    INST1 = 0x20001
    INST2 = 0x20002
    INST3 = 0x20003

    WAITEMPTY_LIST = 0x30000
    WAITFULL_LIST  = 0x30001

    @classmethod
    def try_cast(cls, val):
        try:
            return cls(val)
        except ValueError:
            return val

    @classmethod
    def format_str(cls, val):
        if isinstance(val, cls):
            return val.name
        else:
            return f"{val:#x} (unknown)"

    @property
    def has_instructions(self):
        return self in [self.INST0, self.INST1, self.INST2, self.INST3]

class LEAPFROGSectionFlags(IntEnum):
    ROUTINE = 1

class SectionTypeAdapter(Adapter):
    def _decode(self, obj, ctx, path):
        return LEAPFROGSectionType.try_cast(obj)

    def _encode(self, obj, ctx, path):
        return obj

LEAPFROGSection = Struct(
    "type" / SectionTypeAdapter(Int32ul),
    "load_base" / Int32ul,
    "size" / Int32ul,
    "flags" / Default(Int32ul, 0),
    "data" / Int32ul[this.size],
)

LEAPFROGImage = Struct(
    "magic" / Const(0x1ea9, Int16ul),
    "fmtversion" / Const(0, Int16ul),
    # version 0: in development, no guarantees
    "nsections" / Int32ul,
    "section" / LEAPFROGSection[this.nsections], 
)

Section = LEAPFROGSectionType
SectionFlags = LEAPFROGSectionFlags

class Image:
    def __init__(self):
        self.sections = []
        self.bases = []

    @classmethod
    def read(self, f):
        if type(f) is str:
            with open(f, "rb") as f:
                content = LEAPFROGImage.parse_stream(f)
        elif type(f) in [bytes, bytearray]:
            content = LEAPFROGImage.parse(f)
        else:
            content = LEAPFROGImage.parse_stream(f)

        ret = Image()
        ret.sections = content.section
        ret.bases = []
        ret.index()
        return ret

    @property
    def content(self):
        return Container(
            nsections=len(self.sections),
            section=self.sections,
        )

    def write(self, f):
        if type(f) is str:
            with open(f, "wb") as f:
                LEAPFROGImage.build_stream(self.content, f)
        else:
            LEAPFROGImage.build_stream(self.content, f)


    def __bytes__(self):
        return LEAPFROGImage.build(self.content)

    def index(self):
        self.bases = [
            (sect.type, sect.load_base, sect)
            for sect in self.sections
        ]
        self.bases.sort()

    def reserve(self, type, span, flags=0):
        self.sections.append(Container(
            type=Section.try_cast(type),
            load_base=span.start,
            size=len(span),
            flags=flags,
            data=[0] * len(span),
        ))
        self.index()

    @property
    def routines(self):
        return [range(a, b) for a, b in sorted(set([
            (sect.load_base, sect.load_base + sect.size)
            for sect in self.sections
            if sect.flags & LEAPFROGSectionFlags.ROUTINE
        ]))]

    def section_spans(self, types=None):
        if types is not None:
            types = range(0, 1 << 32)
        return [(t, range(a, b)) for t, a, b in sorted(set([
            (sect.type, sect.load_base, sect.load_base + sect.size)
            for sect in self.sections  if (int(sect.type) in types)
        ]))]

    def dump(self):
        for i, sect in enumerate(self.sections):
            print(f"SECTION {i:d} TYPE {Section.format_str(sect.type)} LOAD BASE {sect.load_base:#x} FLAGS {sect.flags:x}")

            if sect.type in [Section.INST1, Section.INST2, Section.INST3]:
                for off in range(0, sect.size, 16):
                    line = "".join(f"{v:03x} " for v in sect.data[off:off+16])
                    print(f"\t{line}")
            else:
                for off in range(0, sect.size, 8):
                    line = "".join(f"{v:08x} " for v in sect.data[off:off+8])
                    print(f"\t{line}")

    def _lookup_section(self, secttype, addr):
        secttype = Section(secttype)
        idx = bisect.bisect_left(self.bases, (secttype, addr + 1)) - 1
        if idx < 0 or self.bases[idx][0] != secttype:
            return None
        sect = self.bases[idx][2]
        if addr >= sect.load_base + sect.size:
            return None
        assert addr >= sect.load_base
        return sect

    def __getitem__(self, spec):
        assert len(spec) == 2

        if type(spec[0]) in [list, set, range]:
            return [self[secttype,spec[1]] for secttype in spec[0]]
        elif type(spec[0]) is slice:
            return [self[secttype,spec[1]] for secttype \
                    in range(spec[0].start, spec[0].stop)]
        elif type(spec[1]) in [list, set]:
            return [self[spec[0], addr] for addr in spec[1]]
        elif type(spec[1]) in [range, slice]:
            if not (spec[1].stop is None or spec[1].stop > spec[1].start):
                return []
            sect = self._lookup_section(spec[0], spec[1].start)
            if spec[1].stop is None:
                if sect is not None:
                    return sect.data[spec[1].start - sect.load_base:]
                else:
                    return []
            if sect is None:
                raise IndexError(f"no backing for {str(secttype)},{addr} in image")
            elif spec[1].stop > sect.load_base + sect.size:
                # canary for there being a followup section
                self[spec[0],sect.load_base + sect.size]
                # we passed the canary, there's data there but we
                # leave this case unimplemented
                raise NotImplementedError("slice overruns an image section")
            else:
                return sect.data[spec[1].start - sect.load_base \
                                 :spec[1].stop - sect.load_base]
        else:
            sect = self._lookup_section(*spec)
            if sect is None:
                raise IndexError(f"no backing for {spec!r} in image")
            return sect.data[spec[1] - sect.load_base]

    def __setitem__(self, spec, data):
        assert len(spec) == 2

        if type(spec[0]) in [list, set, range]:
            for secttype, subdata in zip(spec[0], data):
                self[secttype, spec[1]] = subdata
        elif type(spec[0]) is slice:
            for secttype, subdata in \
                    zip(range(spec[0].start, spec[0].stop), data):
                self[secttype, spec[1]] = subdata
        elif type(spec[1]) in [list, set]:
            for addr, subdata in zip(spec[1], data):
                self[secttype, addr] = subdata
        elif type(spec[1]) in [range, slice]:
            if not spec[1].stop > spec[1].start:
                return
            sect = self._lookup_section(spec[0], spec[1].start)
            if spec[1].stop > sect.load_base + sect.size:
                # canary for there being a follow-up section
                self[spec[0],sect.load_base + sect.size]
                # we passed the canary, there's data there but we
                # leave this case unimplemented
                raise NotImplementedError("slice overruns an image section")
            sect.data[spec[1].start - sect.load_base: \
                      spec[1].stop - sect.load_base] = data
        else:
            sect = self._lookup_section(*spec)
            if sect is None:
                raise IndexError(f"no backing for {spec!r} in image")
            sect.data[spec[1] - sect.load_base] = data

    def __contains__(self, key):
        return self._lookup_section(*key) is not None

if __name__ == "__main__":
    Image.read(sys.argv[1]).dump()
