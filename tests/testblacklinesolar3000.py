#! /usr/bin/python

import unittest
from solarstats import solarutils
from solarstats import blacklinesolar3000

class TestBlacklinesolar(unittest.TestCase):

    def setUp(self):
        self.su = solarutils.SolarUtils()
        self.bls = blacklinesolar3000.BlackLineSolar()

    def test_calculateModBusCRC(self):
        self.assertEqual(self.bls.calculateModbusCrc("\xFF\x03\x00\x3C\x00\x01"), "\x51\xD8")
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("FF 03 02 00 02")), self.su.hexify("10 51"))
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("02 04 00 00 00 03")), self.su.hexify("B0 38"))
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("02 04 06 42 06 12 43 50 30")), self.su.hexify("3B F9"))
        self.assertEqual(self.bls.calculateModbusCrc("\x02\x04\x00\x2B\x00\x02"), "\x01\xF0")
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("02 04 04 00 1E 01 F7")), self.su.hexify("E8 94"))

    def test_mb_readRegister(self):
        slaveAddress = "FF"
        startRegister = "3C"
        numRegisters = "01"
        self.assertEqual(self.bls.mb_readRegister(slaveAddress, "\x03", startRegister, numRegisters), "\xFF\x03\x00\x3C\x00\x01\x51\xD8")

        startRegister = "00"
        numRegisters = "03"
        self.assertEqual(self.bls.mb_readRegister(slaveAddress, "\x04", startRegister, numRegisters), "\xFF\x04\x00\x00\x00\x03\xA5\xD5")

    def test_mb_readHoldingRegisters(self):
        slaveAddress = "FF"
        startRegister = "3C"
        numRegisters = "01"
        self.assertEqual(self.bls.mb_readHoldingRegisters(slaveAddress, startRegister, numRegisters), "\xFF\x03\x00\x3C\x00\x01\x51\xD8")

    def test_mb_readInputRegisters(self):
        slaveAddress = "FF"
        startRegister = "00"
        numRegisters = "03"
        self.assertEqual(self.bls.mb_readInputRegisters(slaveAddress, startRegister, numRegisters), "\xFF\x04\x00\x00\x00\x03\xA5\xD5")
    
    def test_mb_parseResponse(self):
        self.assertEqual(self.bls.mb_parseResponse("\xFF\x03\x02\x00\x02\x10\x51"), ("\xFF", "\x03", "\x02", "\x00\x02"))
        self.assertEqual(self.bls.mb_parseResponse("\x02\x04\x06\x42\x06\x12\x43\x50\x30\x3B\xF9"), ("\x02", "\x04", "\x06", "\x42\x06\x12\x43\x50\x30"))
        with self.assertRaises(ValueError):
            self.assertEqual(self.bls.mb_parseResponse("\xFF\x03"))
        with self.assertRaises(ValueError):
            self.assertEqual(self.bls.mb_parseResponse("\xFF\x03\x02\x00\x02\x10\x52"))

    def test_busQueryCommand(self):
        self.assertEqual(self.bls.busQueryCommand(), "\xFF\x03\x00\x3C\x00\x01\x51\xD8")
        
    def test_serialNumberQuery(self):
        slaveAddress = "02"
        self.assertEqual(self.bls.serialNumberCommand(slaveAddress), "\x02\x04\x00\x00\x00\x03\xB0\x38")

    def test_modelSWCommand(self):
        slaveAddress = "02"
        self.assertEqual(self.bls.modelSWCommand(slaveAddress), "\x02\x04\x00\x2B\x00\x02\x01\xF0")
