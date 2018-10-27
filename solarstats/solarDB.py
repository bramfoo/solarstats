import sqlite3  # Database connection
import logging
import datetime

dbName = None
conn = None


class SolarDB:
    def __init__(self, sqliteDb):
        global dbName, conn
        dbName = sqliteDb
        conn = sqlite3.connect(dbName)
        logging.info('Connected to SQLite database "%s"', dbName)

    def latestReading(self, inverterID):
        cursor = conn.cursor()

        #latestReading = {}
        #manufacturer = self.getManufacturerByID(inverterID)
        cursor.execute(
            'SELECT max(DateTime) FROM inverterdata where Inverter_ID=?', (inverterID,))
        latestReading = cursor.fetchone()[0]
        #latestReading[inverterID] = {'Manufacturer': manufacturer, 'DateTime':reading}
        logging.debug('Latest reading for inverter %s: %s',
                      inverterID, latestReading)
        cursor.close()
        return latestReading

    def getDistinctIDs(self):
        cursor = conn.cursor()
        # Get unique IDs
        cursor.execute('SELECT DISTINCT id FROM inverter')
        ids = cursor.fetchall()
        logging.debug("Dinstict IDs found: %s", ids)
        cursor.close()
        return ids

    def inverterInfo(self):
        cursor = conn.cursor()
        ids = self.getDistinctIDs()
        inverters = {}
        for id in ids:
            cursor.execute(
                'SELECT Manufacturer, Model FROM invertertype where ID=?', id)
            reading = cursor.fetchone()
            logging.debug("Inverter info: %s", reading)
            inverters[id[0]] = {
                'Manufacturer': reading[0], 'Model': reading[1]}
        cursor.close()
        return inverters

    def getManufacturerByID(self, inverterID):
        cursor = conn.cursor()
        # Get manufacturer belonging to ID
        cursor.execute(
            'SELECT manufacturer FROM invertertype WHERE ID=?', (inverterID,))
        manufacturer = cursor.fetchone()[0]
        cursor.close()
        return manufacturer

    def reading(self, inverterID):
        latest = self.latestReading(inverterID)
        if (latest is None):
            logging.warn("No reading for %s", inverterID)
            return {'Error':'No reading for inverterID {}'.format(inverterID)}
        cursor = conn.cursor()
        cursor.execute(
            'SELECT PowerAC, VoltsPV1, CurrentPV1, EnergyToday, EnergyTotal, MinToday, HrsTotal, Temperature FROM inverterdata WHERE Inverter_ID=? AND DateTime=?', (inverterID, latest))
        query = cursor.fetchone()
        cursor.close()
        results = {}
        electric = {'Power': query[0],
                    'Voltage': query[1], 'Current': query[2]}
        energy = {'Today': query[3], 'Total': query[4]}
        time = {'MinToday': query[5], 'TotalHours': query[6]}

        results[latest] = {
            'Electric': electric, 'Energy': energy, 'Time': time, 'Temperature': query[7]}
        return results

    def latestSomething(self):
        # Retrieve slave address from db
        t = ('1')
        cursor = conn.cursor()
        cursor.execute('SELECT Manufacturer FROM invertertype WHERE ID=?', t)
        slaveAddress = cursor.fetchone()[0]
        logging.info('Using slave addres "%s" from db', slaveAddress)
        if slaveAddress is None:
            print("%s : Cannot read slave address...",
                  (datetime.datetime.now()))
        return slaveAddress

    def status(self):
        return (sqlite3.sqlite_version, dbName)
