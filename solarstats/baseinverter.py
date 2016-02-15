import abc  # Abstract base class

class BaseInverter():
    __metaclass__ = abc.ABCMeta

    @staticmethod
    @abc.abstractmethod
    def queryBusAddress(self, serialPort):
        """Queries the inverter for the bus address. This should be a static method!

        Keyword arguments:
        serialPort -- the linux device (e.g. /dev/ttyUSB1) that is connected to the inverter
        Return values:
        busAddress -- the bus address (in hex) that the inverter needs for data retrieval
        """

    @abc.abstractmethod
    def queryInverterInfo(self):
        """Queries the inverter for the serial number, model and software version of the inverter

        Return values:
        serial -- the unique serial number of the inverter
        model -- the model number of the inverter
        swVer -- the software version running on the inverter
        """

    @abc.abstractmethod
    def getSolarData(self):
        """Retrieves the latest solar data readings from the inverter

        Return values:
        data -- dictionary containing solar data readings
        """
