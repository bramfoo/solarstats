import abc      # Abstract base class
import logging  # General logging
import struct   # Used in the CRC calculation
import bls3000_config as c  # Port configuration and scaling
from solarstats import solarutils
from solarstats.baseinverter import BaseInverter

class BlackLineSolar(BaseInverter):
    # Basic ModBus commands (\x is escape sequence for hex digits)
    read_holding_register = "\x03"
    read_input_register = "\x04"

    su = solarutils.SolarUtils()

    def __init__(self, serialPort, address):
        self.port = serialPort
        self.address = address

# Abstract method implementation
    @staticmethod
    def queryBusAddress(serialPort):
        slaveAddress = "FF"

        #FIXME
        serPort = BlackLineSolar.su.openSerial(serialPort)
        ch = serPort.read()
        return ch;

    def queryInverterInfo(self):
        #FIXME
        pass;

    def getSolarData(self):
        #FIXME
        pass;


    # Calculate the (two hex byte) Modbus CRC. Judiciuously taken from Minimalmodbus [http://minimalmodbus.sourceforge.net/]
    def calculateModbusCrc(self, inputstring):
        POLY = 0xA001 # Constant for MODBUS CRC-16
        register = 0xFFFF # Preload a 16-bit register with ones

        for character in inputstring:
            register = register ^ ord(character) # XOR with each character
            for i in range(8): # Rightshift 8 times, and XOR with polynom if carry overflows
                register, carrybit = self.su.rightshift(register)
                if carrybit == 1:
                    register = register ^ POLY
        # The result is LSB, so swap the bytes
        return struct.pack('<H', register)

    # Generic Read [Holding|Input] Register command (valid for 0x03, 0x04) as per ModBus protocol
    def __readRegister(self, functionCode, startRegister, numRegisters):
        pdu = functionCode + startRegister.zfill(4).decode('hex') + numRegisters.zfill(4).decode('hex')
        adu = self.address.decode('hex') + pdu + self.calculateModbusCrc(self.address.decode('hex') + pdu)
        logging.debug("Command generated: %s ", self.su.printhex(adu))
        return adu

    # Generates the Read Holding Registers command (0x03) as per ModBus protocol
    def readHoldingRegisters(self, startRegister, numRegisters):
        functionCode = self.read_holding_register
        return self.__readRegister(functionCode, startRegister, numRegisters)

    # Generates the Read Input Registers command (0x04) as per ModBus protocol
    def readInputRegisters(self, startRegister, numRegisters):
        functionCode = self.read_input_register
        return self.__readRegister(functionCode, startRegister, numRegisters)

    # Parse response of BLS inverter as per ModBus protocol
    def parseResponse(self, response):
        # Should at least expect 'address', 'function' and 'data length' bytes
        if len(response) < 3:
            logging.error("Error parsing response of length %d", len(response))
            raise ValueError("Response length too short: %d", len(response))

        address = response[0] # First field is address
        command = response[1] # First field is command
        byteCount = response[2] # Second field is byte count
        data = response[3:-2] # Remainder (minus last 2 CRC bytes) is data

        # Check the CRC of the response; if incorrect, do not return message data
        calcCrc = self.calculateModbusCrc(response[:-2])
        if calcCrc != response[-2] + response[-1]:
            logging.error("Invalid CRC (expected: %s; actual: %s)! Ignoring response...", self.su.printhex(calcCrc), self.su.printhex(response[-2] + response[-1]))
            raise ValueError("Invalid CRC (expected: %s; actual: %s))", self.su.printhex(calcCrc), self.su.printhex(response[-2] + response[-1]))

        return (address, command, byteCount, data)


    ###################
    # Specific commands
    ###################

    # Generate busQuery command ("FF 03 00 3C 00 01 51 D8")
    def busQueryCommand(self):
        startRegister = "3C"
        numRegisters = "01"
        return self.readHoldingRegisters(startRegister, numRegisters)

    # Generate serial number query ("02 04 00 00 00 03 B0 38")
    def serialNumberCommand(self):
        startRegister = "00"
        numRegisters = "03"
        return self.readInputRegisters(startRegister, numRegisters)

    # Query model / software version command ("02 04 00 2B 00 02 01 F0")
    def modelSWCommand(self):
        startRegister = "2B"
        numRegisters = "02"
        return self.readInputRegisters(startRegister, numRegisters)

    # Inverter data ("02 04 00 0A 00 1F 91 F3")
    def inverterData(self):
        startRegister = "0A"
        numRegisters = "1F"
        return self.readInputRegisters(startRegister, numRegisters)
