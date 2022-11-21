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

if __name__ == '__main__':
    unittest.main()
