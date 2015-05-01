#! /usr/bin/python

import unittest
from solarstats import mastervoltsoladin600

class TestMastervolt(unittest.TestCase):

    def setUp(self):
        self.mv = mastervoltsoladin600.MasterVolt()

    def test_calcCRC(self):
        self.assertEqual(self.mv.calcCRC("\xFF"), "\x00")
        self.assertEqual(self.mv.calcCRC("\xFF\xFF"), "\xFF")
        self.assertEqual(self.mv.calcCRC("\xFF\xFF\xFF\xFF"), "\xFD")
        self.assertEqual(self.mv.calcCRC("\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"), "\xF9")
        self.assertEqual(self.mv.calcCRC("\x00\x00\x00\x00\x00\x00\x00\x00"), "\x00")
        self.assertEqual(self.mv.calcCRC("\x11\x00\x00\x00\xB6\x00\x00\x00"), "\xC7")

        self.assertNotEqual(self.mv.calcCRC("\x00\x00\x00\x00\x00\x00\x00\x00"), "\x01")

    def test_generateCommand(self):
        slaveAddress   = "00 00"
        sourceAddress = "00 00"
        self.assertEqual(self.mv.generateCommand(slaveAddress, sourceAddress, self.mv.mvCmd_probe), "\x00\x00\x00\x00\xC1\x00\x00\x00\xC1")

        slaveAddress = "11 00"
        self.assertEqual(self.mv.generateCommand(slaveAddress, sourceAddress, self.mv.mvCmd_firmware), "\x11\x00\x00\x00\xB4\x00\x00\x00\xC5")
        
        self.assertEqual(self.mv.generateCommand(slaveAddress, sourceAddress, self.mv.mvCmd_resmax), "\x11\x00\x00\x00\x97\x01\x00\x00\xA9")
        
        
    def test_responseLength(self):
        self.assertEqual(self.mv.responseLength('\x9A'), 8)
        self.assertEqual(self.mv.responseLength('\xB4'), 31)
        self.assertEqual(self.mv.responseLength('\xB6'), 31)
        self.assertNotEqual(self.mv.responseLength('\xB5'), 31)
        self.assertEqual(self.mv.responseLength('\xB7'), 1)

    def test_parseResponse(self):
        self.assertEqual(self.mv.parseResponse("\x00\x00\x11\x00\xC1\xF3\x00\x00\xC5"), ("\x00\x00", "\x11\x00", "\xF3\x00\x00"))
        with self.assertRaises(ValueError):     # Too short
            self.assertEqual(self.mv.parseResponse("\x00\x00\x11\x00"))
        with self.assertRaises(ValueError):     # Incorrect length for command
            self.assertEqual(self.mv.parseResponse("\x00\x00\x11\x00\xB4\xF3\x00\x00\xC5"))
        with self.assertRaises(ValueError):     # Incorrect CRC
            self.assertEqual(self.mv.parseResponse("\x00\x00\x11\x00\xC1\xF3\x00\x00\xC6"))

    def test_busQueryCommand(self):
        self.assertEqual(self.mv.busQueryCommand(), "\x00\x00\x00\x00\xC1\x00\x00\x00\xC1")
        
    def test_serialNumberQuery(self):
        slaveAddress = "11 00"
        self.assertEqual(self.mv.serialNumberCommand(slaveAddress), "\x11\x00\x00\x00\xB4\x00\x00\x00\xC5")

    @unittest.skip("Method not implemented yet")
    def test_modelSWCommand(self):
        slaveAddress = "11 00"
        self.assertEqual(self.mv.modelSWCommand(slaveAddress), "")
