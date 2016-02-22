#! /usr/bin/python

import unittest
import mock
from solarstats import solarutils
from solarstats.blacklinesolar3000 import blacklinesolar3000

class TestBlacklinesolar(unittest.TestCase):

    def setUp(self):
        self.su = solarutils.SolarUtils()
        self.bls = blacklinesolar3000.BlackLineSolar("port", "FF")
        self.bls2 = blacklinesolar3000.BlackLineSolar("port", "02")

    @mock.patch('solarstats.solarutils.serial.Serial')
    def test_queryBusAddress(self, mock_serial):
        mock_serial.return_value.read.return_value = '\xFF'
        self.assertEqual(blacklinesolar3000.BlackLineSolar.queryBusAddress('/dev/ttyUSB0'), '\xFF')

    @mock.patch.object(solarutils.SolarUtils, 'openSerial')
    def test_queryInverterInfo(self, mock_openSerial):
        mock_openSerial.return_value=self.mockSerial()
        self.assertEqual(self.bls.queryInverterInfo(), '\xFF')

    @unittest.skip("Method not implemented yet")
    def test_getSolarData(self):
        self.assertEqual(self.bls.getSolarData(""))

### Private methods. Should probably not be tested
    def test_calculateModBusCRC(self):
        self.assertEqual(self.bls.calculateModbusCrc("\xFF\x03\x00\x3C\x00\x01"), "\x51\xD8")
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("FF 03 02 00 02")), self.su.hexify("10 51"))
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("02 04 00 00 00 03")), self.su.hexify("B0 38"))
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("02 04 06 42 06 12 43 50 30")), self.su.hexify("3B F9"))
        self.assertEqual(self.bls.calculateModbusCrc("\x02\x04\x00\x2B\x00\x02"), "\x01\xF0")
        self.assertEqual(self.bls.calculateModbusCrc(self.su.hexify("02 04 04 00 1E 01 F7")), self.su.hexify("E8 94"))

    def test_readRegister(self):
        startRegister = "3C"
        numRegisters = "01"
        dir(self.bls)
        self.assertEqual(self.bls._BlackLineSolar__readRegister("\x03", startRegister, numRegisters), "\xFF\x03\x00\x3C\x00\x01\x51\xD8")

        startRegister = "00"
        numRegisters = "03"
        self.assertEqual(self.bls._BlackLineSolar__readRegister("\x04", startRegister, numRegisters), "\xFF\x04\x00\x00\x00\x03\xA5\xD5")

    def test_readHoldingRegisters(self):
        startRegister = "3C"
        numRegisters = "01"
        self.assertEqual(self.bls.readHoldingRegisters(startRegister, numRegisters), "\xFF\x03\x00\x3C\x00\x01\x51\xD8")

    def test_readInputRegisters(self):
        startRegister = "00"
        numRegisters = "03"
        self.assertEqual(self.bls.readInputRegisters(startRegister, numRegisters), "\xFF\x04\x00\x00\x00\x03\xA5\xD5")

    def test_parseResponse(self):
        self.assertEqual(self.bls.parseResponse("\xFF\x03\x02\x00\x02\x10\x51"), ("\xFF", "\x03", "\x02", "\x00\x02"))
        self.assertEqual(self.bls.parseResponse("\x02\x04\x06\x42\x06\x12\x43\x50\x30\x3B\xF9"), ("\x02", "\x04", "\x06", "\x42\x06\x12\x43\x50\x30"))
        with self.assertRaises(ValueError):
            self.assertEqual(self.bls.parseResponse("\xFF\x03"))
        with self.assertRaises(ValueError):
            self.assertEqual(self.bls.parseResponse("\xFF\x03\x02\x00\x02\x10\x52"))

    def test_busQueryCommand(self):
        self.assertEqual(self.bls.busQueryCommand(), "\xFF\x03\x00\x3C\x00\x01\x51\xD8")

    def test_serialNumberQuery(self):
        self.assertEqual(self.bls2.serialNumberCommand(), "\x02\x04\x00\x00\x00\x03\xB0\x38")

    def test_modelSWCommand(self):
        self.assertEqual(self.bls2.modelSWCommand(), "\x02\x04\x00\x2B\x00\x02\x01\xF0")


    # Mock serial object. Supports the read/write methods
    class mockSerial(object):
        # instance properties
        _responses = { 'busQuery' : ['\xFF', '\x03', '\x00', '\x3C', '\x00', '\x01', '\x51', '\xD8']}

        def __init__(self):
            response = []

        def read(self):
            if (len(self.response)):
                return self.response.pop(0)
            else:
                return ''

        def write(self, argValue):
            self.response = self._responses[argValue]
