import binascii # Provides unhexlify
import logging  # General logging
import math     # Math utils (pow)


class SolarUtils:
    def __init__(self):
        pass

    # Print a string as uppercase hex characters, without leading '0x'
    # Uses https://docs.python.org/2/library/functions.html#format
    def printhex(self, hexVar):
        if type(hexVar) is int:
            return format(hexVar, '02X')
        if type(hexVar) is str:
            #return ' '.join(format(int(c, 16), '02X') for c in hexVar)   # Fails on long strings
            return ' '.join(format(ord(c), '02X') for c in hexVar)
            #return ' '.join(x.encode('hex') for x in hexVar).upper()  # Original
        if type(hexVar) is unicode:
            #return format(int(hexVar.decode('utf_8'), 16), '02X')
            return str(hexVar.decode()).upper()
        if type(hexVar) is list:
            return " ".join([self.printhex(c) for c in hexVar])
        
        # Fail for all other types
        raise TypeError("Cannot create hex from type: %s ", str(type(hexVar)))

    def hexify(self, data):
        words = data.split()
        result = ''
        for word in words:
            result += binascii.unhexlify(word)
        return result

    # Perform a bitwise right shift. Judiciuously taken from Minimalmodbus [http://minimalmodbus.sourceforge.net/]
    def rightshift(self, inputInteger):
        shifted = inputInteger >> 1
        carrybit = inputInteger & 1
        return shifted, carrybit

    # Convert a hexadecimal value to integer
    def hex2int(self, inp):
        i = 0
        result = 0
        for char in inp:  # Is little-endian, so no need to reverse
            result += int(char.encode('hex'), 16) * math.pow(256, i)
            i += 1
        #logging.debug("Converted hex value %s to int value %d", printhex(input), result)
        return result
        #return int(inp, 16)
        # For \xFF encoded strings: ord('\xFF')
