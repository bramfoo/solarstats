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
        # Return as list instead of tuple (see https://stackoverflow.com/a/23115247)
        conn.row_factory = lambda cursor, row: row[0]
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT id FROM inverter')
        ids = cursor.fetchall()
        logging.debug("Dinstict IDs found: %s", ids)
        # Reset row_factory to return full row
        conn.row_factory = None
        cursor.close()
        return ids

    def inverterInfo(self):
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
                'SELECT ID, Manufacturer, Model FROM invertertype')
        results = cursor.fetchmany(100)
        cursor.close()
        conn.row_factory = None

        logging.debug("Found %s row(s) of inverter data", len(results))        
        inverters = {}
        for row in results:
            inverters[row['ID']] = {
                'Manufacturer': row['Manufacturer'], 'Model': row['Model']}
        return inverters

    def getManufacturerByID(self, inverterID):
        cursor = conn.cursor()
        # Get manufacturer belonging to ID
        cursor.execute(
            'SELECT manufacturer FROM invertertype WHERE ID=?', (inverterID,))
        manufacturer = cursor.fetchone()[0]
        cursor.close()
        return manufacturer

    def reading(self, inverterID, fromDate=None, toDate=None):
        # Check if ID exists
        if (inverterID not in self.getDistinctIDs()):
            logging.warn("No reading for %s", inverterID)
            return {'Error':'No reading for inverterID {}'.format(inverterID)}

        query = 'SELECT DateTime, PowerAC, VoltsPV1, CurrentPV1, EnergyToday, EnergyTotal, MinToday, HrsTotal, Temperature FROM inverterdata WHERE Inverter_ID=?'
        params = (inverterID, )

        if (fromDate is None) and (toDate is None):
            # Return latest value
            queryDate = self.latestReading(inverterID)
            query = query + ' AND DateTime=?'
            params = params + (queryDate,)
        elif (fromDate is not None):
            start = datetime.datetime.strptime(fromDate.replace('"', ''), '%Y-%m-%d %H:%M:%S')
            logging.debug("Time: %s", start)
            query = query + ' AND DateTime>=?'
            params = params + ('{}'.format(start), )
        if (toDate is not None):
            end = datetime.datetime.strptime(toDate.replace('"', ''), '%Y-%m-%d %H:%M:%S')
            query = query + ' AND DateTime<=?'
            params = params + ('{}'.format(end), )
        
        logging.debug("Query: %s; parameters: %s", query, params)

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchmany(100)
        cursor.close()
        conn.row_factory = None

        resultsMap = {}
        if not results:
            logging.warn("No results found for inverterID %s from %s to %s", inverterID, fromDate, toDate)
            return resultsMap

        # Loop over all rows
        for row in results:
            electric = {'Power': row['PowerAC'],
                        'Voltage': row['VoltsPV1'], 'Current': row['CurrentPV1']}
            energy = {'Today': row['EnergyToday'], 'Total': row['EnergyTotal']}
            time = {'MinToday': row['MinToday'], 'TotalHours': row['HrsTotal']}

            resultsMap[row['DateTime']] = {
                'Electric': electric, 'Energy': energy, 'Time': time, 'Temperature': row['Temperature']}
        logging.debug("Found %s rows", len(resultsMap))
        
        return resultsMap

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
