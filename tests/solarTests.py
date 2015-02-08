#! /usr/bin/python

import unittest
import solarutils, mastervolt, blacklinesolar

class TestSolarUtils(unittest.TestCase):

    def setUp(self):
        self.su = solarutils.SolarUtils()

    def test_printHexInt(self):
        self.assertEqual(self.su.printHex(5), "5")
        self.assertNotEqual(self.su.printHex(6), "5")
        self.assertEqual(self.su.printHex(10), "A")
        self.assertNotEqual(self.su.printHex(11), "C")

    def test_printHexUnicode(self):
        self.assertEqual(self.su.printHex(u'5'), "5")
        self.assertNotEqual(self.su.printHex(u'6'), "5")

    def test_printHexStringList(self):
        self.assertEqual(self.su.printHex(["A", "5"]), "41 35")
        self.assertNotEqual(self.su.printHex(["A", "5"]), "40 35")

    @unittest.expectedFailure
    def test_printHexUnsupportedType(self):
        # should raise an exception for unsupported type
        with self.assertRaises(TypeError):
            self.su.printHex(0xA)

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

    def test_hexToInt(self):
        self.assertEqual(self.su.hexToInt(['\x0A']), 10)
        self.assertEqual(self.su.hexToInt(['\xFF']), 255)
        self.assertEqual(self.su.hexToInt(['\x12', '\x34']), 13330)
        self.assertEqual(self.su.hexToInt(['\xAA', '\xAA']), 43690)

class TestMastervolt(unittest.TestCase):

    def setUp(self):
        self.su = solarutils.SolarUtils()
        self.mv = mastervolt.MasterVolt()

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


class TestBlacklinesolar(unittest.TestCase):

    def setUp(self):
        self.su = solarutils.SolarUtils()
        self.bls = blacklinesolar.BlackLineSolar()

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
        
#if __name__ == '__main__':
#    unittest.main()

def suite():
    suiteUtil = unittest.TestLoader().loadTestsFromTestCase(TestSolarUtils)
    suiteMastervolt = unittest.TestLoader().loadTestsFromTestCase(TestMastervolt)
    suiteBLS = unittest.TestLoader().loadTestsFromTestCase(TestBlacklinesolar)
    
    return unittest.TestSuite([suiteUtil, suiteMastervolt, suiteBLS])
    
unittest.TextTestRunner(verbosity=2).run(suite())
