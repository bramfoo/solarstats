#! /usr/bin/python

import unittest
from solarstats import solarutils

class TestSolarUtils(unittest.TestCase):

    def setUp(self):
        self.su = solarutils.SolarUtils()

    def test_printhexInt(self):
        self.assertEqual(self.su.printhex(5), "05")
        self.assertNotEqual(self.su.printhex(6), "05")
        self.assertEqual(self.su.printhex(10), "0A")
        self.assertNotEqual(self.su.printhex(11), "0C")

    def test_printhexUnicode(self):
        self.assertEqual(self.su.printhex(u'5'), "5")
        self.assertNotEqual(self.su.printhex(u'6'), "05")

    def test_printhexStringList(self):
        self.assertEqual(self.su.printhex(["A", "5"]), "41 35")
        self.assertNotEqual(self.su.printhex(["A", "5"]), "40 35")

    @unittest.expectedFailure
    def test_printhexUnsupportedType(self):
        # should raise an exception for unsupported type
        with self.assertRaises(TypeError):
            self.su.printhex(0xA)

    def test_hexifyString(self):
        self.assertEqual(self.su.hexify("41"), '\x41')
        self.assertNotEqual(self.su.hexify("40"), '\x42')
        self.assertEqual(self.su.hexify("FF 03 02 00 02"), '\xFF\x03\x02\x00\x02')
        self.assertEqual(self.su.hexify("FE03020001"), '\xFE\x03\x02\x00\x01')

        self.assertEqual(self.su.hexify("4135"), '\x41\x35')
        self.assertNotEqual(self.su.hexify("4136"), '\x41\x35')

        # Only even-length strings accepted
        with self.assertRaises(TypeError):
            self.su.hexify("513")

    def test_rightshift(self):
        self.assertEqual(self.su.rightshift(2), (1, 0))
        self.assertEqual(self.su.rightshift(15), (7, 1))
        self.assertNotEqual(self.su.rightshift(8), (1, 0))

    def test_hex2int(self):
        self.assertEqual(self.su.hex2int(['\x0A']), 10)
        self.assertEqual(self.su.hex2int(['\xFF']), 255)
        self.assertEqual(self.su.hex2int(['\x12', '\x34']), 13330)
        self.assertEqual(self.su.hex2int(['\xAA', '\xAA']), 43690)
