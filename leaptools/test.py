import unittest
from construct import hexundump

from .program import *
from .image import Image, Section
from .dsl import Builder

class TestInstruction(unittest.TestCase):
    def test_encoding(self):
        cases = [
            (0x22f4c6, 2,  0,  0),
            (0xa7e5, 6, 13, 5),
            (0xbaded8, 51, 22, 52),
        ]
        for case in cases:
            self.assertEqual(
                case,
                Instruction.decode(*case).encode()
            )

class TestImage(unittest.TestCase):
    def test_image(self):
        img = Image()
        img.reserve(Section.INST0, range(0x0, 0x100))
        img.reserve(Section.INST1, range(0x1000, 0x1100))
        img.reserve(Section.INST1, range(0x0, 0x100))

        img[Section.INST0:Section.INST1 + 1,
            0x0:0x100] = [list(range(0x0, 0x100)), list(range(0x100, 0x200))]
        img[Section.INST1,0x1022] = 0x11

        pieces = [Section.INST0, Section.INST1]
        self.assertEqual(img[pieces, 0x33], [0x33, 0x133])
        self.assertEqual(img[pieces, 0x90:], \
                         [list(range(0x90, 0x100)), list(range(0x190, 0x200))])

        self.assertEqual(img[Section.INST1, 0x1021], 0x00)
        self.assertEqual(img[Section.INST1, 0x1022], 0x11)

class TestProgramImage(unittest.TestCase):
    IMAGE = hexundump("""
0000   08 F1 A9 1E 00 00 00 00 00 00 00 00 00 00 00 00   ................
0010   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
0020   00 00 00 00 00 00 00 00 11 00 00 00 01 00 01 00   ................
0030   01 00 00 00 01 00 00 00 00 00 00 00 00 00 00 40   ...............@
0040   02 00 01 00 02 00 00 00 02 00 00 00 00 00 00 00   ................
0050   01 00 00 00 00 00 00 41 03 00 01 00 02 00 00 00   .......A........
0060   07 00 00 00 00 00 00 00 00 00 00 41 00 00 00 42   ...........A...B
0070   01 00 00 00 00 00 00 42 00 00 00 41 00 00 00 42   .......B...A...B
0080   00 00 00 40 00 00 02 00 00 00 00 00 0A 00 00 00   ...@............
0090   00 00 00 00 A2 B0 00 00 A2 F0 00 00 82 4E 00 00   .............N..
00A0   9C 87 08 00 FF F8 0C 00 A6 23 00 00 A6 31 00 00   .........#...1..
00B0   A1 38 00 00 A1 38 00 00 A5 1B 00 00 01 00 02 00   .8...8..........
00C0   00 00 00 00 0A 00 00 00 00 00 00 00 00 00 00 00   ................
00D0   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
00E0   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
00F0   01 00 00 00 02 00 02 00 00 00 00 00 0A 00 00 00   ................
0100   00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00   ................
0110   00 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00   ................
0120   01 00 00 00 01 00 00 00 01 00 00 00 03 00 02 00   ................
0130   00 00 00 00 0A 00 00 00 00 00 00 00 02 00 00 00   ................
0140   03 00 00 00 00 00 00 00 04 00 00 00 00 00 00 00   ................
0150   01 00 00 00 05 00 00 00 06 00 00 00 07 00 00 00   ................
0160   01 00 00 00 00 00 03 00 00 00 00 00 08 00 00 00   ................
0170   01 00 00 00 00 00 00 00 00 00 00 00 00 00 0A 00   ................
0180   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
0190   00 00 00 00 01 00 03 00 00 00 00 00 04 00 00 00   ................
01A0   00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00   ................
01B0   00 00 00 00 02 00 03 00 00 00 00 00 04 00 00 00   ................
01C0   00 00 00 00 00 00 00 00 00 00 00 00 06 00 00 00   ................
01D0   00 00 00 00 00 00 02 00 0B 00 00 00 01 00 00 00   ................
01E0   00 00 00 00 A0 30 00 00 01 00 02 00 0B 00 00 00   .....0..........
01F0   01 00 00 00 00 00 00 00 00 00 00 00 02 00 02 00   ................
0200   0B 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00   ................
0210   03 00 02 00 0B 00 00 00 01 00 00 00 00 00 00 00   ................
0220   08 00 00 00 00 00 03 00 00 00 01 00 08 00 00 00   ................
0230   01 00 00 00 00 00 00 00 00 00 00 00 0B 00 0C 00   ................
0240   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
0250   00 00 00 00 01 00 03 00 00 00 01 00 04 00 00 00   ................
0260   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
0270   00 00 00 00 02 00 03 00 00 00 01 00 04 00 00 00   ................
0280   00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00   ................
0290   00 00 00 00                                       ....

""", linesize=0x10)

    def test_program_from_image_and_back(self):
        img = Image.read(self.IMAGE)
        prg = Program.from_image(img)
        img_redone = prg.build_image()
        self.assertEqual(bytes(img_redone), bytes(img))

if __name__ == '__main__':
    unittest.main()
