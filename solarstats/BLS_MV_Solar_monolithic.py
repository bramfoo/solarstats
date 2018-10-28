#! /usr/bin/python
# This script does some basic Modbus communications with the BlackLine Solar 3000

# Import Python modules
import argparse
import binascii
import datetime
import logging
import fnmatch
import math
import os
import serial
import sqlite3
import subprocess
import sys
import time
import shutil
import string
import struct

read_mastervolt = "\x11\x00\x00\x00\xB6\x00\x00\x00\xC7"

# FIXME: Move to config.json
# Program data
logFile = "SolarStats.log"
sqliteDbName = 'SolarStats.sqlt'
workingDir = '/home/pi/'
webDir = '/var/www/'
# Time (in seconds) between data requests; used in RRDtool, set as cron interval
step = 300
retries = 3          # Number of times to retry (on failure) before giving up
bls2013 = 2188.7
sol2013 = 364.31


def parseArgs():
    """ Parse command line arguments (http://docs.python.org/2/library/argparse.html#the-add-argument-method) """
    parser = argparse.ArgumentParser(
        description='Read and store data from the BlackLine Solar 3000 PV inverter')
    parser.add_argument('-g', '--graph', action='store_true',
                        help='Draws the RRDtool graphs')
    parser.add_argument('-t', '--test', action='store_true',
                        help='Run the testing function (beta!)')
    args = parser.parse_args()

    logging.info("Args parsed: %s", args)
    return args

# Send a hexadecimal command to a given port


def sendCommand(port, command):
    logging.info("Sending command to serial port: %s ", printHex(command))
    port.write(command)


def osUptime():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        uptime_string = str(datetime.timedelta(seconds=uptime_seconds))

    return uptime_string

# FIXME: Move to DB class


def latestDbVals(inverter, columnName, useDate):
    currdate = str(datetime.date.today().strftime("%Y-%m-%d")) + "%"
    conn = sqlite3.connect(sqliteDbName)
    cursor = conn.cursor()
    logging.debug("Querying inverter %s for %s on date %s",
                  inverter, columnName, currdate)
    # Parameters cannot be used for column names (http://stackoverflow.com/questions/13880786/python-sqlite3-string-variable-in-execute)
    if useDate:
        cursor.execute("SELECT max(" + columnName +
                       ") FROM inverterdata WHERE inverter_ID=? AND DateTime LIKE ?", (inverter, currdate))
    else:
        cursor.execute("SELECT max(" + columnName +
                       ") FROM inverterdata WHERE inverter_ID=?", (inverter,))
    value = cursor.fetchone()[0]
    logging.debug("Database result: %s", value)
    conn.close()
    if value is None:
        return 0
    else:
        return str(value)

    ###
    # BLS3000
    ###
    serPort = openSerial('/dev/ttyUSB0')
    if serPort is None:
        print("%s : Cannot open serial port, exiting..." %
              (datetime.datetime.now()))
        sys.exit()

    # Probe inverter for default data to be added to SQLite tables
    # Send busQuery command ("FF 03 00 3C 00 01 51 D8")
    logging.debug("Sending bus query application data unit (ADU)")
    slaveAddress = "FF"
    startRegister = "3C"
    numRegisters = "01"
    command = mb_ReadHoldingRegisters(
        slaveAddress, startRegister, numRegisters)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)
    # Expected response: FF 03 02 00 02 10 51
    logging.info("Bus query response (data): %s", printHex(rData))
    logging.info("Using this response as slave address: %s",
                 printHex(rData[1]))
    slaveAddress = rData[1].encode('hex')

    # Query serial number ("02 04 00 00 00 03 B0 38")
    logging.debug("Sending serial number query ADU")
    startRegister = "00"
    numRegisters = "03"
    command = mb_ReadInputRegisters(slaveAddress, startRegister, numRegisters)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)
    # Expected response: 02 04 06 42 06 12 43 50 30 3B F9
    logging.info("Serial number response (data): %s", printHex(rData))
    serialNumber = printHex(rData).replace(" ", "")

    # Query model / software version command ("02 04 00 2B 00 02 01 F0")
    logging.debug("Sending model/software command ADU")
    # slaveAddress unchanged
    startRegister = "2B"
    numRegisters = "02"
    command = mb_ReadInputRegisters(slaveAddress, startRegister, numRegisters)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)
    # Expected response: 02 04 04 00 1E 01 F7 E8 94
    logging.info("Model/software response (data): %s", printHex(rData))
    model = str(int(rData[0].encode('hex') +
                    rData[1].encode('hex'), 16) / 10.0) + 'kW'
    swVersion = str(int(rData[2].encode('hex') +
                        rData[3].encode('hex'), 16) / 100.0)

    # Push data into db
    conn = sqlite3.connect(sqliteDbName)
    cursor = conn.cursor()
    logging.info('Connected to SQLite database "%s"', sqliteDbName)

    t = ('1', serialNumber, '1')
    cursor.execute("INSERT INTO inverter VALUES (?,?,?)", t)
    conn.commit()
    logging.info('Committed serial number "%s" to database', serialNumber)

    t = ('1', 'KLNE', model, slaveAddress, swVersion, '3000W')
    cursor.execute("INSERT INTO invertertype VALUES (?,?,?,?,?,?)", t)
    conn.commit()
    logging.info('Committed model "%s", slave address "%s", software version "%s" to database',
                 model, slaveAddress, swVersion)
    conn.close()
    logging.debug('Closed connection to database')

    serPort.close()

    ###
    # Soladin600
    ###
    serPort = openSerial('/dev/ttyUSB1')
    if serPort is None:
        print("%s : Cannot open serial port, exiting..." %
              (datetime.datetime.now()))
        sys.exit()

    # Probe inverter for default data to be added to SQLite tables
    # Send busQuery command ("00 00 00 00 C1 00 00 00 C1")
    logging.debug("Sending Soladin probe")
    sourceAddress = "00 00"
    slaveAddress = "00 00"
    command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_probe)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    dest, src, response = mv_parseResponse(bytes, mvCmd_probe)
    # Expected response: 00 00 11 00 C1 F3 00 00 C5
    logging.info("Soladin response (source address): %s", printHex(src))
    logging.info("Using this value as slave address: %s", printHex(src))
    slaveAddress = printHex(src)

    # Query firmware number ("11 00 00 00 B4 00 00 00 C5")
    logging.debug("Sending firmware info/date")
    command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_firmware)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    dest, src, response = mv_parseResponse(bytes, mvCmd_firmware)
    # Expected response:
    logging.info("Serial number response (data): %s", printHex(response))
    swVersion = (printHex(response[11]) + printHex(response[10])) / 100.0
    # No serialNumber available
    serialNumber = swVersion = printHex(response[11]) + printHex(
        response[10]) + "_" + printHex(response[13]) + printHex(response[12])
    logging.info("Using this value as serial number: %s", swVersion)

    # Push data into db
    conn = sqlite3.connect(sqliteDbName)
    cursor = conn.cursor()
    logging.info('Connected to SQLite database "%s"', sqliteDbName)

    t = ('2', serialNumber, '2')
    cursor.execute("INSERT INTO inverter VALUES (?,?,?)", t)
    conn.commit()
    logging.info('Committed serial number "%s" to database', swVersion)

    model = '600'
    t = ('2', 'Soladin', model, slaveAddress, swVersion, '600W')
    cursor.execute("INSERT INTO invertertype VALUES (?,?,?,?,?,?)", t)
    conn.commit()
    logging.info('Committed model "%s", slave address "%s", software version "%s" to database',
                 model, slaveAddress, swVersion)
    conn.close()
    logging.debug('Closed connection to database')

    # Add cronjob:
    # >crontab -e
    # >*/5 * * * * /home/pi/BLS_SolarStats.py >> /home/pi/SolarConsole.log 2>&1
    # >crontab -l (list jobs)

# Run a testing function


def testInverter():

    serPort = openSerial('/dev/ttyUSB1')
    if serPort is None:
        print("%s : Cannot open serial port USB1..." %
              (datetime.datetime.now()))

    slaveAddress = "11 00"
    sourceAddress = "00 00"
    command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_stats)
    sendCommand(serPort, command)
    #bytes = serPort.readline()
    bytes = receiveCommand(serPort)
    #bytes = serPort.read(1000)
    print("Open? " + str(serPort.isOpen()))
    print("Received: " + printHex(bytes) + "(len: " + str(len(bytes)) + ")")
    serPort.close()


"""
#These are the remaining BLS registers

    slaveAddress = "02"
    # 02 04 00 29 00 1F 60 39
    print "Querying input register 0x29 - 0x47"
    startRegister = "29"
    numRegisters = "1F"
    queryPrintRegister(serPort, slaveAddress, startRegister, numRegisters)

    # 02 04 00 3A 00 17 90 3A
    print "Querying input register 0x3A - 0x50"
    startRegister = "3A"
    numRegisters = "17"
    queryPrintRegister(serPort, slaveAddress, startRegister, numRegisters)

def queryPrintRegister(serPort, slaveAddress, startRegister, numRegisters):
    command = mb_ReadInputRegisters(slaveAddress, startRegister, numRegisters)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)

    i = 0;
    address = "0x" + str(startRegister)
    print "Results: "
    while i < int((rByteCount.encode('hex')), 16):
        print "[" + str(address) + "]\t -> [" + str(printHex(rData[i] + rData[i+1])) + "] ("+ str(int(rData[i].encode('hex') + rData[i+1].encode('hex'), 16)) + "d)"
        address = hex(int(address, 16) + 1)
        i += 2
"""


########
### MAIN
########
if __name__ == "__main__":
    # Log file for reference
    logging.basicConfig(filename=logFile, level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('Logging started...')

    # Script-specific 'cronjobs'
    hour = datetime.datetime.now().hour
    minute = datetime.datetime.now().minute

    args = parseArgs()

    if args.test:
        testInverter()
        sys.exit()

    # Create graphs every hour, or when asked by the user
    if (args.graph or minute == 0):
        logging.debug(
            "Creating RRD graphs (crontime is %s:%s)...", hour, minute)
        epochNow = int(time.time())  # Seconds since epoch
        logging.info("Creating RRD graphs, using end time %i", epochNow)
        rrd_graph('solarStats_last24hrs.png', epochNow -
                  60*60*24, epochNow, 'Last 24 hours')
        rrd_graph('solarStats_last7days.png', epochNow -
                  60*60*24*7, epochNow, 'Last 7 days')
        rrd_graph('solarStats_last30days.png', epochNow -
                  60*60*24*30, epochNow, 'Last 30 days')
        rrd_graph('solarStats_lastyear.png', epochNow -
                  60*60*24*365, epochNow, 'Last year')
        if args.graph:
            sys.exit()

    # FIXME: Add temperature/sun up/sun down?
    # See http://www.wunderground.com/weather/api/d/pricing.html?MR=1
    # or http://www.jsunnyreports.com/index.php/category/jsunnyreports/ (direct: http://morpheus.flitspaal.nl/)
    # FIXME: Add all results (once decoded): Status1, ...

    # Open database
    conn = sqlite3.connect(sqliteDbName)
    cursor = conn.cursor()
    logging.info('Connected to SQLite database "%s"', sqliteDbName)
    print("Using log file '" + logFile + "'; database '" +
          sqliteDbName + "'; RRD files '" + rrdDbBLS + "'; '" + rrdDbSol + "'")

    # Blackline Solar
    serPort = openSerial('/dev/ttyUSB0')
    if serPort is None:
        print("%s : Cannot open serial port USB0..." %
              (datetime.datetime.now()))

    # Retrieve slave address from db
    t = ('1')
    cursor.execute('SELECT BusAddress FROM invertertype WHERE ID=?', t)
    slaveAddress = cursor.fetchone()[0]
    logging.info('Using slave addres "%s" from db', printHex(slaveAddress))
    if slaveAddress is None:
        print("%s : Cannot read slave address..." % (datetime.datetime.now()))

    resultsBLS = {}
    resultsBLS['name'] = "BLS3000"
    resultsBLS['success'] = False
    while retries != 0:
        if serPort is None:
            logging.error("No serial port available, aborting data query...")
            retries = 0
            continue
        rData = 0

        # Inverter data ("02 04 00 0A 00 1F 91 F3")
        logging.debug("Sending inverter data request ADU")
        startRegister = "0A"
        numRegisters = "1F"
        command = mb_ReadInputRegisters(
            slaveAddress, startRegister, numRegisters)
        sendCommand(serPort, command)
        bytes = receiveCommand(serPort)

        rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)
        if rData == -1:  # CRC error, break here to retry command
            retries -= 1
            logging.error(
                "CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if rData is None:  # Message error, break here to stop loop
            retries -= 1
            logging.error(
                "Message error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        logging.info("Inverter data response (data): %s", printHex(rData))
        # Success, so no need for retries
        retries = 0
        resultsBLS['success'] = True

        # Decode inverter data
        logging.debug("Decoding inverter data response...")
        i = 0
        address = 0x0A
        while i < int((rByteCount.encode('hex')), 16):
            name = portContents[address]
            if (name == 'blank') or (name == 'unknown'):
                i += 2
                address += 1
                continue

            # Some items are double words, so add the previously added item
            if resultsBLS.has_key(name):
                resultsBLS[name] = ((resultsBLS[name] * scaleFactors[name]) + int(
                    rData[i].encode('hex') + rData[i+1].encode('hex'), 16)) / scaleFactors[name]
            else:
                resultsBLS[name] = int(rData[i].encode(
                    'hex') + rData[i+1].encode('hex'), 16) / scaleFactors[name]
            i += 2
            address += 1

        logging.info("Decoded inverter data response: %s", resultsBLS)
        #print "%s : %s" % (datetime.datetime.now(), resultsBLS)

        # Parse the status. Note that we're inverting the status here for the HTML page (0 = success)
        resultsBLS['statusText'] = 'Unknown: ' + str(resultsBLS['Status2'])
        #FIXME use case
        if resultsBLS['Status2'] == 0:
            resultsBLS['statusText'] = "Inverter not running"
        if resultsBLS['Status2'] == 1:
            resultsBLS['statusText'] = "Inverter in operation"

        # Write results to SQLite
        t = ('1', str(datetime.datetime.now()), resultsBLS['VoltsPV1'], resultsBLS['VoltsPV2'], resultsBLS['CurrentPV1'], resultsBLS['CurrentPV2'], resultsBLS['VoltsAC1'], resultsBLS['VoltsAC2'], resultsBLS['VoltsAC3'], resultsBLS['CurrentAC1'], resultsBLS['CurrentAC2'], resultsBLS['CurrentAC3'],
             resultsBLS['FrequencyAC'], resultsBLS['PowerAC'], resultsBLS['EnergyToday'], resultsBLS['EnergyTotal'], resultsBLS['MinToday'], resultsBLS['HrsTotal'], resultsBLS['Temperature'], resultsBLS['Iac-Shift'], resultsBLS['DCI'], resultsBLS['Status1'], resultsBLS['Status2'], printHex(rData))
        logging.debug("Writing results to database: %s", t)

        cursor.execute(
            "INSERT INTO inverterdata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
        conn.commit()
        logging.debug("Data committed to database")

    # while retries
    logging.info("Closing connection to serial port")
    if serPort is not None:
        serPort.close()

    # Write results to RRD db -- update using time of 'now' (N). Lifted from solget.sh
    rrdWrite = str(0) + ":" + str(0) + ":" + str(0)
    if resultsBLS['success']:
        rrdWrite = str(resultsBLS['PowerAC']) + ":" + str(
            resultsBLS['EnergyToday']) + ":" + str(resultsBLS['EnergyTotal'] - bls2013)
    try:
        rrdResult = subprocess.call(
            ['rrdtool', 'update', rrdDbBLS, 'N:' + rrdWrite])
        logging.debug(
            "Data (%s) committed to RRD database; exit code is %s", rrdWrite, rrdResult)
    except subprocess.CalledProcessError as inst:
        logging.error('Error writing data to RRD: %s', inst.args[0])

    # Soladin
    serPort = openSerial('/dev/ttyUSB1')
    if serPort is None:
        print("%s : Cannot open serial port USB1..." %
              (datetime.datetime.now()))

    # Retrieve slave address from db
    t = ('2')
    cursor.execute('SELECT BusAddress FROM invertertype WHERE ID=?', t)
    slaveAddress = cursor.fetchone()[0]
    logging.info('Using slave addres "%s" from db', printHex(slaveAddress))
    if slaveAddress is None:
        print("%s : Cannot read slave address..." % (datetime.datetime.now()))

    retries = 3
    sourceAddress = "00 00"
    resultsSol = {}
    resultsSol['name'] = "Soladin600"
    resultsSol['success'] = False
    while retries != 0:
        if serPort is None:
            logging.error("No serial port available, aborting data query...")
            retries = 0
            continue
        command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_stats)
        sendCommand(serPort, command)
        bytes = receiveCommand(serPort)
        dest, src, response = mv_parseResponse(bytes, mvCmd_stats)
        if response == -1:  # CRC error, break here to retry command
            retries -= 1
            logging.error(
                "CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if response is None:  # Message error, break here to stop loop
            retries -= 1
            logging.error(
                "Message error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue

        # Decode inverter data
        logging.debug("Decoding mv_inverter data response...")
        statBits = hexToInt(response[1:3])               # 1,2
        uSol = hexToInt(response[3:5]) / 10.0            # 3,4
        iSol = hexToInt(response[5:7]) / 100.0           # 5,6
        fNet = hexToInt(response[7:9]) / 100.0           # 7,8
        uNet = hexToInt(response[9:11]) / 1.0            # 9,10
        wSol = hexToInt(response[13:15]) / 1.0           # 13,14
        wTot = hexToInt(response[15:18]) / 100.0         # 15,16,17
        tSol = hexToInt(response[18]) / 1.0              # 18
        # 19,20,21; minutes to hours
        hTot = hexToInt(response[19:22]) / 60.0

        resultsSol["VoltsPV1"] = uSol
        resultsSol["CurrentPV1"] = iSol
        resultsSol["VoltsAC1"] = uNet
        resultsSol["FrequencyAC"] = fNet
        resultsSol["Status1"] = 0
        resultsSol["Status2"] = statBits
        resultsSol["PowerAC"] = wSol
        resultsSol["Temperature"] = tSol
        resultsSol["EnergyTotal"] = wTot
        resultsSol["HrsTotal"] = hTot

        # Parse the status.
        #FIXME use case
        resultsSol['statusText'] = 'Unknown: ' + str(statBits)
        if statBits == 0:
            resultsSol['statusText'] = "Inverter in operation"
        elif statBits & 0x001:
            resultsSol['statusText'] = "Solar input voltage too high"
        elif statBits & 0x002:
            resultsSol['statusText'] = "Solar input voltage too low"
        elif statBits & 0x004:
            resultsSol['statusText'] = "No input from mains"
        elif statBits & 0x008:
            resultsSol['statusText'] = "Mains voltage too high"
        elif statBits & 0x010:
            resultsSol['statusText'] = "Mains voltage too low"
        elif statBits & 0x020:
            resultsSol['statusText'] = "Mains frequency too high"
        elif statBits & 0x040:
            resultsSol['statusText'] = "Mains frequency too low"
        elif statBits & 0x080:
            resultsSol['statusText'] = "Temperature error"
        elif statBits & 0x100:
            resultsSol['statusText'] = "Hardware error"
        elif statBits & 0x200:
            resultsSol['statusText'] = "Starting up"
        elif statBits & 0x400:
            resultsSol['statusText'] = "Max solar output"
        elif statBits & 0x800:
            resultsSol['statusText'] = "Max output"

        """
        print "Stat:\t" + str(statBits)
        print "Panel volt:\t" + str(uSol)
        print "Panel curr:\t" + str(iSol)
        print "Panel pwr:\t" + str(uSol*iSol)
        print "Net freq:\t" + str(fNet)
        print "Net volt:\t" + str(uNet)
        print "Convert pwr:\t" + str(wSol)
        print "Convert temp:\t" + str(tSol)
        print "Convert total:\t" + str(wTot)
        print "Runtime:\t" + str(hTot)
        """

        command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_maxpow)
        sendCommand(serPort, command)
        bytes = receiveCommand(serPort)
        dest, src, response2 = mv_parseResponse(bytes, mvCmd_maxpow)
        if response2 == -1:  # CRC error, break here to retry command
            retries -= 1
            logging.error(
                "CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if response2 is None:  # Message error, break here to stop loop
            retries -= 1
            logging.error(
                "Message error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue

        mPow = hexToInt(response2[19:21]) / 1.0
        # print "MaxPow:\t" + str(mPow)

        command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_hisdat)
        sendCommand(serPort, command)
        bytes = receiveCommand(serPort)
        dest, src, response3 = mv_parseResponse(bytes, mvCmd_hisdat)
        if response3 == -1:  # CRC error, break here to retry command
            retries -= 1
            logging.error(
                "CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if response3 is None:  # Message error, break here to stop loop
            retries -= 1
            logging.error(
                "Message error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue

        mTod = hexToInt(response3[0]) * 5.0  # Daily operation * 5 minutes
        wTod = hexToInt(response3[1]) / 100.0
        #print "Min today:\t" + str(mTod)
        #print "Pwr today:\t" + str(wTod)
        results2 = [statBits, uSol, iSol, fNet, uNet, wSol,
                    wTot, tSol, hTot, "$", mPow, "$", mTod, wTod]
        logging.info("Decoded inverter data response: %s", results2)
        resultsSol['EnergyToday'] = wTod
        resultsSol['MinToday'] = mTod

        response = printHex(response) + " $ " + \
            printHex(response2) + " $ " + printHex(response3)
        logging.info("Inverter data response (data): %s", printHex(response))
        # Success, so no need for retries
        retries = 0
        resultsSol['success'] = True

        conn = sqlite3.connect(sqliteDbName)
        cursor = conn.cursor()
        logging.info('Connected to SQLite database "%s"', sqliteDbName)

        t = ('2', str(datetime.datetime.now()), uSol, '0.0', iSol, '0.0', uNet, '0.0', '0.0', '0.0',
             '0.0', '0.0', fNet, wSol, wTod, wTot, mTod, hTot, tSol, '0.0', '0.0', statBits, '0.0', response)
        logging.debug("Writing results to database: %s", t)

        cursor.execute(
            "INSERT INTO inverterdata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
        conn.commit()
        logging.debug("Data committed to database")

    # while retries
    logging.info("Closing connection to serial port")
    if serPort is not None:
        serPort.close()

    # Write results to RRD db -- update using time of 'now' (N). Lifted from solget.sh
    rrdWrite = str(0) + ":" + str(0) + ":" + str(0)
    if resultsSol['success']:
        rrdWrite = str(resultsSol["PowerAC"]) + ":" + str(
            resultsSol['EnergyToday']) + ":" + str(resultsSol["EnergyTotal"] - sol2013)
    try:
        rrdResult = subprocess.call(
            ['rrdtool', 'update', rrdDbSol, 'N:' + rrdWrite])
        logging.debug(
            "Data (%s) committed to RRD database; exit code is %s", rrdWrite, rrdResult)
    except subprocess.CalledProcessError as inst:
        logging.error('Error writing data to RRD: %s', inst.args[0])

    # End of day checks: archive graphs
    if (hour == 23 and minute == 55):
        # Copy the file to the 'archive' directory
        logging.info("%s:%s: archiving graphs to '%s'",
                     hour, minute, rrdArchDir)
        filenames = os.listdir(webDir)
        logging.debug("Found files: '%s'", filenames)
        try:
            for imgName in fnmatch.filter(filenames, 'solarStats*.png'):
                root, ext = os.path.splitext(imgName)
                shutil.copy(os.path.join(webDir, imgName), os.path.join(
                    os.getcwd(), rrdArchDir, root + "_" + str(time.strftime("%Y-%m-%d")) + ext))
                logging.debug(
                    "Copying/renaming file '%s' from '%s' to '%s'", imgName, webDir, rrdArchDir)
        except IOError as inst:
            logging.error("Cannot copy/archive file '%s' from '%s' to '%s': %s",
                          imgName, webDir, rrdArchDir, inst.args[0])

    # Closedown
    logging.info("Closing connection to database")
    conn.close()
