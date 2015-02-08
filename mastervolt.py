import logging  # General logging
import struct   # Used in the CRC calculation
from solarutils import SolarUtils

class MasterVolt:
    def __init__(self):
        # Basic Mastervolt commands 
        self.mvCmd_probe    = "\xC1"
        self.mvCmd_firmware = "\xB4"
        self.mvCmd_stats    = "\xB6"
        self.mvCmd_maxpow   = "\xB9"
        self.mvCmd_resmax   = "\x97"
        self.mvCmd_hisdat   = "\x9A"

        self.su = SolarUtils()

    # Calculates the (single hex byte) CRC of a given hexadecimal
    def calcCRC(self, data):
        crc = 0x00
        for char in data[:-1]:
            crc += ord(char)
            crc = crc & 0xFF
        return chr(crc)

    # Generates a command to send to the Soladin600
    def generateCommand(self, sourceAddress, slaveAddress, cmd):
        filler = self.su.hexify('00 00 00')
        if cmd == '\x97':
            filler = self.su.hexify('01 00 00')
        command = self.su.hexify(sourceAddress) + self.su.hexify(slaveAddress) + cmd + filler
        command = command + self.calcCRC(command)
        return command

    # Expected response lengths for specific commands
    def responseLength(self, cmd):
        return {
                  '\x97' : 9,
                  '\x9A' : 8,
                  '\xB4' : 31,
                  '\xB6' : 31,
                  '\xB9' : 31,
                  '\xC1' : 9,
            }.get(cmd, 1)    # 1 is default if cmd not found

    # Parse the Soladin response. Checks for correct response length, as well as CRC.
    # Returns (source, destination, data)
    def parseResponse(self, response):
        # Fifth byte is the function code, each of which has a certain response length
        if len(response) < 5:
            logging.error("Response too short (%d) to determine function code", len(response))
            raise ValueError("Response too short (%d) to determine function code", len(response))
            
        # Should expect at least a certain number of bytes
        fc = response[4]
        minLength = self.responseLength(fc)
        if len(response) < minLength:
            logging.error("Error parsing response of length %d, expecting at least %d bytes", len(response), minLength)
            raise ValueError("Expected response length of %d for function %s, actual response length was %d", minLength, self.su.printHex(fc), len(response)) 

        # Check the CRC of the response; if incorrect, do not return message data
        calcCrc = self.calcCRC(response)
        if calcCrc != response[-1]:
            logging.error("Invalid CRC (expected: %s; actual: %s)! Ignoring response...", self.su.printHex(calcCrc), self.su.printHex(response[-1]))
            raise ValueError("Invalid CRC (expected: %s; actual: %s)", self.su.printHex(calcCrc), self.su.printHex(response[-1])) 
        #logging.debug("Calculated crc: %s; actual: %s", self.su.printHex(calcCrc), self.su.printHex(response[-1]))
        
        # Return source, destination and data (remove function and crc)
        return response[0:2], response[2:4], response[5:-1]

        ###################
        # Specific commands
        ###################

    # Generate busQuery command ("00 00 00 00 C1 00 00 00 C1")
    def busQueryCommand(self):
        slaveAddress   = "00 00"
        sourceAddress = "00 00"
        return self.generateCommand(slaveAddress, sourceAddress, self.mvCmd_probe)

    # Query firmware number ("11 00 00 00 B4 00 00 00 C5")
    def serialNumberCommand(self, slaveAddress):
        sourceAddress = "00 00"
        return self.generateCommand(slaveAddress, sourceAddress, self.mvCmd_firmware)

    # FIXME: Provide a response for this command
    def modelSWCommand(self, slaveAddress):
        pass

"""
===          
Soladin decoding [https://github.com/teding/SolaDin]
Note: contains some errors (missing '00' in filler)
===
Commands
  DA=destAddress; SA=srcAddress FC=functionCode, CR=crc
  DA DA SA SA FC  ?  ?  ? CR
  00 00 00 00 C1 00 00 00 C1 - probe           (RX: 00 00 11 00 C1 F3 00 00 C5)
  11 00 00 00 B4 00 00 00 C5 - firmware        (RX: 00 00 11 00 B4 F3 00 00 00 00 00 00 00 E3 00 04 01 34 06 00 00 00 00 00 00 00 00 00 00 00 DA)
  11 00 00 00 B6 00 00 00 C7 - stats           (RX: 00 00 11 00 B6 F3 00 00 04 03 35 00 8A 13 F4 00 00 00 24 00 90 0B 00 1F DB BC 01 00 00 00 FD)
  11 00 00 00 B9 00 00 00 CA - max power       (RX: 00 00 11 00 B9 F3 00 00 20 00 00 00 1B 00 21 00 22 00 00 00 E5 02 7E 48 36 00 00 00 00 00 1E
  11 00 00 00 97 01 00 00 A9 - reset max power (RX: 00 00 11 00 97 01 00 00 A9)
  11 00 00 00 9A 00 00 AB    - history (0x05 is day, where 0 is today, 9 is 9 days before (RX: 00 00 11 00 9A 54 05 04)
  
Flags
Flags are bit mapped and represent current status of the inverter. Normal opartion of the inverter is 
identified with no flag being set.
0x0001: Usolar too high
0x0002: Usolar too low
0x0004: No Grid
0x0008: Uac too high
0x0010: Uac too low
0x0020: Fac too high
0x0040: Fac too low
0x0080: Temperature too high
0x0100: Hardware failure
0x0200: Starting
0x0400: Max power
0x0800: Max current
"""
