#! /usr/bin/python
# This script does some basic Modbus communications with the BlackLine Solar 3000

# FIXME: Modularise: main() report()

# Import Python modules
import argparse, binascii, datetime, logging, fnmatch, math, os, serial, sqlite3, subprocess, sys, time, shutil, string, struct

# Basic ModBus commands (\x is escape sequence for hex digits)
read_holding_register = "\x03"
read_input_register = "\x04"

# Basic Mastervolt commands 
mvCmd_probe = "\xC1"
mvCmd_firmware = "\xB4"
mvCmd_stats = "\xB6"
mvCmd_maxpow = "\xB9"
mvCmd_resmax = "\x97"
mvCmd_hisdat = "\x9A"

read_mastervolt="\x11\x00\x00\x00\xB6\x00\x00\x00\xC7"


# Program data
logFile        = "SolarStats.log"
sqliteInitFile = 'SolarStatsInit.sql'
sqliteDbName   = 'SolarStats.sqlt'
rrdDbBLS      = 'SolarStats_BLS.rrd'
rrdDbSol      = 'SolarStats_Sol.rrd'
workingDir     = '/home/pi/'
rrdArchDir     = 'rrdGraphs/'
webDir         = '/var/www/'
step           = 300        # Time (in seconds) between data requests; used in RRDtool, set as cron interval
retries        = 3          # Number of times to retry (on failure) before giving up
bls2013        = 2188.7
sol2013        = 364.31

# BlackLine Solar 3000 port and value maps
portContents = {0x0A : 'VoltsPV1',
                0x0B : 'VoltsPV2',
                0x0C : 'CurrentPV1',
                0x0D : 'CurrentPV2',
                0x0E : 'VoltsAC1',
                0x0F : 'VoltsAC2',
                0x10 : 'VoltsAC3',
                0x11 : 'CurrentAC1',
                0x12 : 'CurrentAC2',
                0x13 : 'CurrentAC3',
                0x14 : 'FrequencyAC',
                0x15 : 'PowerAC',
                0x16 : 'PowerAC',
                0x17 : 'EnergyToday',
                0x18 : 'EnergyTotal',
                0x19 : 'EnergyTotal',
                0x1A : 'MinToday',
                0x1B : 'MinToday',
                0x1C : 'HrsTotal',
                0x1D : 'HrsTotal',
                0x1E : 'Temperature',
                0x1F : 'Iac-Shift',
                0x20 : 'blank',
                0x21 : 'blank',
                0x22 : 'DCI',
                0x23 : 'blank',
                0x24 : 'blank',
                0x25 : 'blank',
                0x26 : 'blank',
                0x27 : 'Status1',
                0x28 : 'Status2',
                }

scaleFactors = {'VoltsPV1'      : 10.0,
                'VoltsPV2'      : 10.0,
                'CurrentPV1'    : 10.0,
                'CurrentPV2'    : 10.0,
                'VoltsAC1'      : 10.0,
                'VoltsAC2'      : 10.0,
                'VoltsAC3'      : 10.0,
                'CurrentAC1'    : 10.0,
                'CurrentAC2'    : 10.0,
                'CurrentAC3'    : 10.0,
                'FrequencyAC'   : 100.0,
                'PowerAC'       : 10.0,
                'EnergyToday'   : 10.0,
                'EnergyTotal'   : 10.0,
                'MinToday'     : 1.0,
                'HrsTotal'     : 1.0,
                'Temperature'   : 10.0,
                'Iac-Shift'     : 1.0,
                'blank'         : 1.0,
                'blank'         : 1.0,
                'DCI'           : 1.0,
                'Status1'        : 1,
                'Status2'        : 1,
                }

def parseArgs():
    """ Parse command line arguments (http://docs.python.org/2/library/argparse.html#the-add-argument-method) """
    parser = argparse.ArgumentParser(description='Read and store data from the BlackLine Solar 3000 PV inverter')
    parser.add_argument('-c', '--create', action='store_true', help='Creates and initialises the SQLite and RRDtool databases')
    parser.add_argument('-g', '--graph', action='store_true', help='Draws the RRDtool graphs')
    parser.add_argument('-e', '--export', action='store_true', help='Export the SQLite inverter power data')
    parser.add_argument('-t', '--test', action='store_true', help='Run the testing function (beta!)')
    args = parser.parse_args()
    
    logging.info("Args parsed: %s", args)
    return args                

# Connection details for the serial port; opens the port immediately
# http://tubifex.nl/2013/04/read-mastervolt-soladin-600-with-python-pyserial/
def openSerial(portID):
    try:
        serPort = serial.Serial(
            port=portID,
            baudrate=9600,
            timeout=0.5,  # Increase this if timing is too low to get a response
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
    except (ValueError, serial.SerialException) as inst:
        logging.error('Error opening serial port: %s', inst.args[0])
        return None

    logging.info("Using serial port %s", str(serPort))
    return serPort
    
# Print a string as uppercase hex characters, without leading '0x'
# FIXME
def printHex(hexVar):
    if type(hexVar) is int:
        return str(hex(hexVar)[2:]).upper()
    if type(hexVar) is unicode:
        return str(hexVar.decode()).upper()
    if type(hexVar) not in [list, str]:
        logging.error("Cannot create hex from type: %s ", str(type(hexVar)))
        return None

    return ' '.join(x.encode('hex') for x in hexVar).upper()

def hexify(data):
    words = data.split()
    result = ''
    for word in words:
        result += binascii.unhexlify(word)
    return result

# Send a hexadecimal command to a given port
def sendCommand(port, command):
    logging.info("Sending command to serial port: %s ", printHex(command))
    port.write(command)

# Read characters from a given port until no more are received
def receiveCommand(port):
    data = []
    ch = port.read()
    while len(ch) != 0:
        data.append(ch)
        ch = port.read()
    
    if len(data) > 0:
        logging.info("Received: %s [len = %d]", printHex(data), len(data))
    else:
        logging.warning("Serial port command requested, but none received")
    
    return data

# Perform a bitwise right shift. Judiciuously taken from Minimalmodbus [http://minimalmodbus.sourceforge.net/]        
def rightshift(inputInteger):
    shifted = inputInteger >> 1
    carrybit = inputInteger & 1
    return shifted, carrybit 
        
# Calculate the Modbus CRC. Judiciuously taken from Minimalmodbus [http://minimalmodbus.sourceforge.net/]        
def calculateModbusCrc(inputstring):
    POLY = 0xA001 # Constant for MODBUS CRC-16
    register = 0xFFFF # Preload a 16-bit register with ones
    
    for character in inputstring:
        register = register ^ ord(character) # XOR with each character
        for i in range(8): # Rightshift 8 times, and XOR with polynom if carry overflows
            register, carrybit = rightshift(register)
            if carrybit == 1:
                register = register ^ POLY
    # The result is LSB, so swap the bytes
    return struct.pack('<H', register)

# Generic Read [Holding|Input] Register command (valid for 0x03, 0x04) as per ModBus protocol
def mb_readRegister(slaveAddress, functionCode, startRegister, numRegisters):
    pdu = functionCode + startRegister.zfill(4).decode('hex') + numRegisters.zfill(4).decode('hex')
    adu = slaveAddress.decode('hex') + pdu + calculateModbusCrc(slaveAddress.decode('hex') + pdu)
    logging.debug("Command generated: %s ", printHex(adu))
    return adu

# Generates the Read Holding Registers command (0x03) as per ModBus protocol
def mb_ReadHoldingRegisters(slaveAddress, startRegister, numRegisters):
    functionCode = "\x03"
    return mb_readRegister(slaveAddress, functionCode, startRegister, numRegisters)

# Generates the Read Input Registers command (0x04) as per ModBus protocol
def mb_ReadInputRegisters(slaveAddress, startRegister, numRegisters):
    functionCode = "\x04"
    return mb_readRegister(slaveAddress, functionCode, startRegister, numRegisters)

def mb_parseResponse(response):
    # Should at least expect 'address', 'function' and 'data length' bytes
    if len(response) < 3: 
        logging.error("Error parsing response of length %d", len(response))
        return (None, None, None, None)
    
    address = response[0] # First field is address
    command = response[1] # First field is command
    byteCount = response[2] # Second field is byte count
    data = response[3:-2] # Remainder (minus last 2 CRC bytes) is data

    # Check the CRC of the response; if incorrect, do not return message data
    calcCrc = calculateModbusCrc(response[:-2])
    if calcCrc != response[-2] + response[-1]:
        logging.warning("Invalid CRC (expected: %s; actual: %s)! Ignoring response...", printHex(calcCrc), printHex(response[-2] + response[-1]))
        return (address, command, -1, -1)

    return (address, command, byteCount, data)

def mv_calcCRC(data):
    crc = 0x00
    for char in data[:-1]:
        crc += ord(char)
        crc = crc & 0xFF
    return chr(crc)

def mv_generateCommand(sourceAddress, slaveAddress, cmd):
    filler = hexify('00 00 00')
    if cmd == '\x97':
        filler = hexify('10 00 00')
    command = hexify(sourceAddress) + hexify(slaveAddress) + cmd + filler
    command = command + mv_calcCRC(command)
    return command

def mv_responseLength(cmd):
    return {
              '\x97' : 9,
              '\x9A' : 8,
              '\xB4' : 31,
              '\xB6' : 31,
              '\xB9' : 31,
              '\xC1' : 9,
        }.get(cmd, 1)    # 1 is default if cmd not found

def mv_parseResponse(response, cmd):
	# Should expect at least a certain number of bytes
    minLength = mv_responseLength(cmd)
    if len(response) < minLength:
        logging.error("Error parsing response of length %d, expecting at least %d bytes", len(response), minLength)
        return None, None, None
    # Check the CRC of the response; if incorrect, do not return message data
    calcCrc = mv_calcCRC(response)
    if calcCrc != response[-1]:
        logging.warning("Invalid CRC (expected: %s; actual: %s)! Ignoring response...", printHex(calcCrc), printHex(response[-1]))
        return None
    #logging.debug("Calculated crc: %s; actual: %s", printHex(calcCrc), printHex(response[-1]))
    
    # Return source, destination and data (remove function and crc)
    return response[0:2], response[2:4], response[5:-1]
    
# Generate RRD graphs. Lifted from solget.sh and http://sourceforge.net/apps/mediawiki/linknx/index.php?title=How_to_create_graphs_with_RRDTool
def rrd_graph(imgName, startTime, endTime, imgTitle):
    
    # Create a RRDtool graph, using the Linux command
    # `rrdtool graph <imgName> --start <start> --end <end> --imgformat PNG --width 500 --height 250 --title <title> --lower-limit 0 --rigid --units-exponent 0 --vertical-label Watt DEF:bls5avg=SolarStats.rrd:bls3000:AVERAGE LINE1:bls5avg#0000FF:"Solar Power output" DEF:bls5max=SolarStats.rrd:bls3000:MAX:start=end-1y LINE1:bls5max#00FF00:"Solar Power max" DEF:bls5min=SolarStats.rrd:bls3000:MIN:start=end-1y LINE1:bls5min#FF0000:"Solar Power min" COMMENT:"Generated on <time>"
    # Averages plotted are year-long averages
    
    try:
        if (endTime - startTime) < 60*60*24*7*2:    # 24hr / 7 day graphs
            rrdResult = subprocess.call(['rrdtool', 'graph', str(imgName), '--start', str(startTime), '--end', str(endTime), '--imgformat', 'PNG', '--width', str(720), '--height', str(250), '--title', str(imgTitle), '--units-exponent', str(0), '--vertical-label', 'Solar Power (Watt)', '--right-axis-label', 'Daily yield (kWh)', '--right-axis', '0.005:0', '--right-axis-format', '%1.0lf', 'DEF:bls=' + rrdDbBLS + ':bls3000_pow:LAST', 'DEF:bls_nrg=' + rrdDbBLS + ':bls3000_nrg:LAST', 'DEF:sol=' + rrdDbSol + ':sol600_pow:LAST', 'DEF:sol_nrg=' + rrdDbSol + ':sol600_nrg:LAST', 'VDEF:bls_avg=bls,AVERAGE', 'VDEF:bls_max=bls,MAXIMUM', 'VDEF:bls_last=bls,LAST', 'VDEF:sol_avg=sol,AVERAGE', 'VDEF:sol_max=sol,MAXIMUM', 'VDEF:sol_last=sol,LAST', 'VDEF:bls_nrg_max=bls_nrg,MAXIMUM', 'VDEF:sol_nrg_max=sol_nrg,MAXIMUM', 'CDEF:scaled_bls_nrg=bls_nrg,200,*',  'CDEF:scaled_sol_nrg=sol_nrg,200,*', 'LINE1:bls#0000FF:Actual (BLS)\\t', 'GPRINT:bls_last:%2.1lf W\\t\\t', 'LINE1:sol#FF0066:Actual (Sol)\\t', 'GPRINT:sol_last:%2.1lf W\\n', 'LINE1:bls_avg#FF6600:Average (BLS)\\t', 'GPRINT:bls_avg:%2.1lf W\\t\\t', 'LINE1:sol_avg#FF6600:Average (Sol)\\t:dashes', 'GPRINT:sol_avg:%2.1lf W\\n', 'LINE1:bls_max#00CC00:Maximum (BLS)\\t', 'GPRINT:bls_max:%2.1lf W\\t', 'LINE1:sol_max#00CC00:Maximum (Sol)\\t:dashes', 'GPRINT:sol_max:%2.1lf W\\n', 'LINE1:scaled_bls_nrg#00CCFF:Yield (BLS)\\t', 'GPRINT:bls_nrg_max:%2.1lf kWh\\t\\t', 'LINE1:scaled_sol_nrg#FF66FF:Yield (Sol)\\t', 'GPRINT:sol_nrg_max:%2.1lf kWh\\n', 'COMMENT:Generated on ' + str(time.strftime("%B %d, %Y (%H\:%M)"))])
        else:
            rrdResult = subprocess.call(['rrdtool', 'graph', str(imgName), '--start', str(startTime), '--end', str(endTime), '--imgformat', 'PNG', '--width', str(720), '--height', str(250), '--title', str(imgTitle), '--units-exponent', str(0), '--vertical-label', 'Solar Power (Watt)', '--right-axis-label', 'Total yield (kWh)', '--right-axis', '1:0', '--right-axis-format', '%1.0lf', 'DEF:bls=' + rrdDbBLS + ':bls3000_pow:LAST', 'DEF:bls_tot=' + rrdDbBLS + ':bls3000_tot:LAST', 'DEF:sol=' + rrdDbSol + ':sol600_pow:LAST', 'DEF:sol_tot=' + rrdDbSol + ':sol600_tot:LAST', 'VDEF:bls_avg=bls,AVERAGE', 'VDEF:bls_max=bls,MAXIMUM', 'VDEF:bls_last=bls,LAST', 'VDEF:sol_avg=sol,AVERAGE', 'VDEF:sol_max=sol,MAXIMUM', 'VDEF:sol_last=sol,LAST', 'VDEF:bls_tot_max=bls_tot,LAST', 'VDEF:sol_tot_max=sol_tot,LAST', 'CDEF:scaled_bls_tot=bls_tot,1,*',  'CDEF:scaled_sol_tot=sol_tot,1,*', 'LINE1:bls#0000FF:Actual (BLS)\\t', 'GPRINT:bls_last:%2.1lf W\\t\\t', 'LINE1:sol#FF0066:Actual (Sol)\\t', 'GPRINT:sol_last:%2.1lf W\\n', 'LINE1:bls_avg#FF6600:Average (BLS)\\t', 'GPRINT:bls_avg:%2.1lf W\\t\\t', 'LINE1:sol_avg#FF6600:Average (Sol)\\t:dashes', 'GPRINT:sol_avg:%2.1lf W\\n', 'LINE1:bls_max#00CC00:Maximum (BLS)\\t', 'GPRINT:bls_max:%2.1lf W\\t', 'LINE1:sol_max#00CC00:Maximum (Sol)\\t:dashes', 'GPRINT:sol_max:%2.1lf W\\n', 'LINE1:scaled_bls_tot#00CCFF:Yield (BLS)\\t', 'GPRINT:bls_tot_max:%2.1lf kWh\\t\\t', 'LINE1:scaled_sol_tot#FF66FF:Yield (Sol)\\t', 'GPRINT:sol_tot_max:%2.1lf kWh\\n', 'COMMENT:Generated on ' + str(time.strftime("%B %d, %Y (%H\:%M)"))])
        logging.debug("Graph %s created; exit code is %s", imgName, rrdResult)
    except subprocess.CalledProcessError as inst:
        logging.error('Error creating RRD graph: %s', inst.args[0])
    
    # Move the files to the web directory
    try: 
        os.rename(os.path.join(workingDir, imgName), os.path.join(webDir, imgName))  # Using rename instead of move to enforce overwriting
        logging.debug("Moving graph to '%s'", webDir)
    except IOError as inst:
        logging.error("Cannot move graph to '%s': %s", webDir, inst.args[0])
        print "%s : Cannot move graph!" % (datetime.datetime.now())

def osUptime():        
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        uptime_string = str(datetime.timedelta(seconds = uptime_seconds))

    return uptime_string

# Generate HTML page. Lifted from solget.sh        
# The kWh->CO2 conversion factor (0.44548) is taken from http://www.carbontrust.com/media/18223/ctl153_conversion_factors.pdf 
def createHTML(iv1, iv2):
    tempFile = 'index.tmp'
    
    uptime = osUptime()
    ivFirstHeader = '<TR><TD>PV Power</TD><TD>PV Voltage</TD><TD>PV Current</TD><TD>Temperature</TD><TD>Net Frequency</TD><TD>Net Voltage</TD></TR>\n'
    ivSecondHeader = '<TR><TD colspan="3"><CENTER>Today</CENTER></TD><TD colspan="3"><CENTER>Total</CENTER></TD></TR>\n'
    ivSecondHeader += '<TR><TD>Time</TD><TD>Delivery</TD><TD>CO&#8322; reduction</TD><TD>Time</TD><TD>Delivery</TD><TD>CO&#8322; reduction</TD></TR>\n'
    
    htmlDest = os.path.join(webDir, 'index.html')
    logging.debug("Creating HTML code in '%s'", tempFile)
    with open(tempFile, 'w') as htmlFile:
        htmlFile.write('<HTML><HEAD><TITLE>Home PV measurements</TITLE></HEAD>\n')
        htmlFile.write('<BODY BGCOLOR="000066" TEXT="#E8EEFD" LINK="#FFFFFF" VLINK="#C6FDF4" ALINK="#0BBFFF" BACKGROUND="$BGIMG">\n')
        htmlFile.write('<TABLE BORDER=1 CELLPADDING=1 CELLSPACING=2 BGCOLOR="#1A689D" BORDERCOLOR="#0DD3EA" ALIGN="center">\n')
        htmlFile.write('<TR><TD colspan="6"><CENTER><font size=5>Home PV</font><BR><font size=-1> Last update: ' + str(time.asctime()) + '</font></CENTER></TD><TR>\n')
        htmlFile.write('<TR><TD colspan="6"><CENTER>.</CENTER></TD></TR>\n')
        
        yearly = [bls2013, sol2013]
        i = 1
        for iv in (iv1, iv2):
            htmlFile.write('<TR><TD>.</TD><TD colspan="4"><CENTER><font size=4>' + iv['name'] + '<BR>')
            if iv['success']:
                htmlFile.write('<font size=-1>' + iv['statusText'] + '</CENTER></FONT></TD><TD>.</TD><TR>\n')
            else:
                htmlFile.write('<FONT size=-1 COLOR=red>Inverter off (using last working values)</CENTER></FONT></TD><TD>.</TD><TR>\n')
            if iv['success']:
                htmlFile.write(ivFirstHeader)
                htmlFile.write('<TR><TD>' + str(iv['PowerAC']) + ' W</TD><TD>' + str(iv['VoltsPV1']) + ' V</TD><TD>' + str(iv['CurrentPV1']) + ' A</TD><TD>' + str(iv['Temperature']) + ' &deg;C</TD><TD>' + str(iv['FrequencyAC']) + ' Hz</TD><TD>' + str(iv['VoltsAC1']) + ' V</TD></TR>\n')
            htmlFile.write(ivSecondHeader)
            if iv['success']:
                minToday = str(int(iv['MinToday']/60)) + ':' + str(int(iv['MinToday'] % 60)).zfill(2)
                energToday = str(iv['EnergyToday'])
                coToday = str("{0:.2f}".format(iv['EnergyToday'] * 0.44548))
                hrsTotal = str(int(iv['HrsTotal'])) + ':00'
                energTotal = str(iv['EnergyTotal'] - yearly[i - 1])
                coTotal = str("{0:.2f}".format(iv['EnergyTotal'] * 0.44548))
            else:
                dbMinToday = int(latestDbVals(i, "MinToday", True))
                minToday = str(int(dbMinToday)/60) + ':' + str(int(dbMinToday % 60)).zfill(2)
                energToday = str(latestDbVals(i, "EnergyToday", True))
                coToday = str("{0:.2f}".format(float(energToday) * 0.44548))
                hrsTotal = str(latestDbVals(i, "HrsTotal", False)) + ':00'
                energTotal = str(float(latestDbVals(i, "EnergyTotal", False)) - yearly[i - 1])
                coTotal = str("{0:.2f}".format(float(energTotal) * 0.44548))
            htmlFile.write('<TR><TD>' + minToday + '</TD><TD>'  + energToday + ' kWh</TD><TD>' + coToday + ' kg</TD><TD>' + hrsTotal + '</TD><TD>' + energTotal + ' kWh <br/> 2013: ' + str(yearly[i - 1]) + ' kWh</TD><TD>' + coTotal +' kg</TD><TR>')
            i += 1
        
        # Remaining table
        htmlFile.write('</TABLE><BR><CENTER><font size=-1>Uptime: ' + uptime + '</font>\n')
        htmlFile.write('<BR><BR>\n')
        htmlFile.write('<FORM><INPUT TYPE="button" VALUE="Refresh" onClick="window.location.reload()" ></FORM><BR>')
        htmlFile.write('<IMG src="solarStats_last24hrs.png" alt="Last 24 hours"><BR><BR>\n')
        htmlFile.write('<IMG src="solarStats_last7days.png" alt="Last 7 days"><BR><BR>\n')
        htmlFile.write('<IMG src="solarStats_last30days.png" alt="Last 30 days"><BR><BR>\n')
        htmlFile.write('<IMG src="solarStats_lastyear.png" alt="Last 365 days"><BR><BR>\n')
        htmlFile.write('<BR><font size=-1>The Dilapidation Crew - 2013</font></center></body></html>\n')

    try: 
        shutil.move(tempFile, htmlDest)
        logging.debug("Moving complete HTML page from  '%s' to '%s'", tempFile, htmlDest)
    except IOError as inst:
        logging.error("Cannot move HTML page from  '%s' to '%s': %s", tempFile, htmlDest, inst.args[0])
        print "%s : Cannot move HTML page!" % (datetime.datetime.now())
        
    return

def latestDbVals(inverter, columnName, useDate):
    currdate = str(datetime.date.today().strftime("%Y-%m-%d")) + "%"
    conn = sqlite3.connect(sqliteDbName)
    cursor = conn.cursor()
    logging.debug("Querying inverter %s for %s on date %s", inverter, columnName, currdate)
    # Parameters cannot be used for column names (http://stackoverflow.com/questions/13880786/python-sqlite3-string-variable-in-execute)
    if useDate:
        cursor.execute("SELECT max(" + columnName + ") FROM inverterdata WHERE inverter_ID=? AND DateTime LIKE ?", (inverter, currdate))
    else:
        cursor.execute("SELECT max(" + columnName + ") FROM inverterdata WHERE inverter_ID=?", (inverter,))
    value = cursor.fetchone()[0]
    logging.debug("Database result: %s", value)
    conn.close()
    if value is None:
        return 0
    else:
        return str(value)
    

# Initialise. Runs the SQLite, RRDtool database generation. Needs to only run once, or when a reset is required.
def createDbs():
    # Create a SQLite database, using the Linux command 
    # `sqlite3 SolarStats.sqlt < SolarStatsInit.sql`
    if os.path.isfile(sqliteInitFile):
        try:
            with open(sqliteInitFile, 'r') as initFile:
                sqlResult = subprocess.call(['sqlite3', sqliteDbName], stdin=initFile)
                logging.info("Attempt to create SQLite db %s: exit code is %s", sqliteDbName, sqlResult)
        except subprocess.CalledProcessError as inst:
            logging.error('Error creating SQLite db: %s', inst.args[0])
    else:
        logging.error("Cannot create SQLite database, init file does not exist: %s", sqliteInitFile)
        print "Cannot create SQLite database, init file does not exist: %s" % sqliteInitFile
        sys.exit(1)

    # Create a RRDtool database, using the Linux command
    # `rrdtool create SolarStats_BLS.rrd --step 300 DS:bls3000:GAUGE:600:U:U RRA:LAST:0.5:1:288 RRA:LAST:0.5:6:336 RRA:MIN:0.5:6:336 RRA:AVERAGE:0.5:6:336 RRA:MAX:0.5:6:336 RRA:LAST:0.5:12:720 RRA:MIN:0.5:12:720 RRA:AVERAGE:0.5:12:720 RRA:MAX:0.5:12:720 RRA:LAST:0.5:288:365 RRA:MIN:0.5:288:365 RRA:AVERAGE:0.5:288:365 RRA:MAX:0.5:288:365`
    # This provides 24hrs, 7day, 30day, 1year data sets

    try:
        rrdResult = subprocess.call(['rrdtool', 'create', rrdDbBLS, '--step', str(step), 'DS:bls3000:GAUGE:600:U:U', 'RRA:LAST:0.5:1:288', 'RRA:LAST:0.5:6:336', 'RRA:MIN:0.5:6:336', 'RRA:AVERAGE:0.5:6:336', 'RRA:MAX:0.5:6:336', 'RRA:LAST:0.5:12:720', 'RRA:MIN:0.5:12:720', 'RRA:AVERAGE:0.5:12:720', 'RRA:MAX:0.5:12:720', 'RRA:LAST:0.5:288:365', 'RRA:MIN:0.5:288:365', 'RRA:AVERAGE:0.5:288:365', 'RRA:MAX:0.5:288:365'])
        logging.info("Attempt to create RRDtool db %s: exit code is %s", rrdDbBLS, rrdResult)
    except subprocess.CalledProcessError as inst:
        logging.error('Error creating RRDtool db: %s', inst.args[0])
        print 'Error creating RRDtool db: %s' % inst.args[0]
        sys.exit(1)

    ###
    # BLS3000
    ###    
    serPort = openSerial('/dev/ttyUSB0')
    if serPort is None:
        print "%s : Cannot open serial port, exiting..." % (datetime.datetime.now())
        sys.exit()

    # Probe inverter for default data to be added to SQLite tables
    # Send busQuery command ("FF 03 00 3C 00 01 51 D8")
    logging.debug("Sending bus query application data unit (ADU)")
    slaveAddress = "FF"
    startRegister = "3C"
    numRegisters = "01"
    command = mb_ReadHoldingRegisters(slaveAddress, startRegister, numRegisters)
    sendCommand(serPort, command)
    bytes = receiveCommand(serPort)
    rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)
    # Expected response: FF 03 02 00 02 10 51
    logging.info("Bus query response (data): %s", printHex(rData))
    logging.info("Using this response as slave address: %s", printHex(rData[1]))
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
    model = str(int(rData[0].encode('hex') + rData[1].encode('hex'), 16) / 10.0) + 'kW'
    swVersion = str(int(rData[2].encode('hex') + rData[3].encode('hex'), 16) / 100.0)
    
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
    logging.info('Committed model "%s", slave address "%s", software version "%s" to database', model, slaveAddress, swVersion)
    conn.close()
    logging.debug('Closed connection to database')

    serPort.close()

    ###
    # Soladin600
    ###    
    serPort = openSerial('/dev/ttyUSB1')
    if serPort is None:
        print "%s : Cannot open serial port, exiting..." % (datetime.datetime.now())
        sys.exit()
    
    # Probe inverter for default data to be added to SQLite tables
    # Send busQuery command ("00 00 00 00 C1 00 00 00 C1")
    logging.debug("Sending Soladin probe")
    sourceAddress = "00 00"
    slaveAddress   = "00 00"
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
    serialNumber = swVersion = printHex(response[11]) + printHex(response[10]) + "_" + printHex(response[13]) + printHex(response[12])
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
    logging.info('Committed model "%s", slave address "%s", software version "%s" to database', model, slaveAddress, swVersion)
    conn.close()
    logging.debug('Closed connection to database')

    # Add cronjob:
    # >crontab -e
    # >*/5 * * * * /home/pi/BLS_SolarStats.py >> /home/pi/SolarConsole.log 2>&1
    # >crontab -l (list jobs)


# Exports the SQLite power data into a flat text file, using Unix epoch time
def exportData():
    exportFile = 'solar.dmp'
    conn = sqlite3.connect(sqliteDbName)
    cursor = conn.cursor()
    logging.info('Connected to SQLite database "%s"', sqliteDbName)
    
    # Retrieve power data from db
    with open(exportFile, 'w') as dumpFile:
        for row in cursor.execute('SELECT DateTime, PowerAC FROM inverterdata ORDER BY DateTime'):
            unixTime = int(time.mktime(datetime.datetime.strptime(row[0].decode(), "%Y-%m-%d %H:%M:%S.%f").timetuple()))
            dumpFile.write('rrdtool update ' + rrdDbBLS + ' ' + str(unixTime) + ":" + str(row[1]) + '\n')

def hexToInt(input):
    i = 0
    result = 0
    for char in input:  # Is little-endian, so no need to reverse
        result += int(char.encode('hex'), 16) * math.pow(256, i)
        i += 1
    #logging.debug("Converted hex value %s to int value %d", printHex(input), result)
    return result

# Run a testing function
def testInverter():

    serPort = openSerial('/dev/ttyUSB1')
    if serPort is None:
        print "%s : Cannot open serial port USB1..." % (datetime.datetime.now())

    slaveAddress = "11 00"
    sourceAddress = "00 00"
    command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_stats)
    sendCommand(serPort, command)
    #bytes = serPort.readline()
    bytes = receiveCommand(serPort)
    #bytes = serPort.read(1000)
    print "Open? " + str(serPort.isOpen())
    print "Received: " + printHex(bytes) + "(len: " + str(len(bytes)) + ")"
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
if __name__=="__main__":
    # Log file for reference
    logging.basicConfig(filename=logFile, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('Logging started...')

    # Script-specific 'cronjobs'
    hour = datetime.datetime.now().hour
    minute = datetime.datetime.now().minute

    args = parseArgs()

    if args.create:
        createDbs()
        sys.exit()

    if args.export:
        exportData()
        sys.exit()

    if args.test:
        testInverter()
        sys.exit()

    # Create graphs every hour, or when asked by the user
    if (args.graph or minute == 0):
        logging.debug("Creating RRD graphs (crontime is %s:%s)...", hour, minute)
        epochNow=int(time.time()) # Seconds since epoch
        logging.info("Creating RRD graphs, using end time %i", epochNow)
        rrd_graph('solarStats_last24hrs.png', epochNow - 60*60*24, epochNow, 'Last 24 hours')
        rrd_graph('solarStats_last7days.png', epochNow - 60*60*24*7, epochNow, 'Last 7 days')
        rrd_graph('solarStats_last30days.png', epochNow - 60*60*24*30, epochNow, 'Last 30 days')
        rrd_graph('solarStats_lastyear.png', epochNow - 60*60*24*365, epochNow, 'Last year')
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
    print "Using log file '" + logFile + "'; database '" + sqliteDbName + "'; RRD files '" + rrdDbBLS + "'; '" + rrdDbSol + "'"

    # Blackline Solar
    serPort = openSerial('/dev/ttyUSB0')
    if serPort is None:
        print "%s : Cannot open serial port USB0..." % (datetime.datetime.now())

    # Retrieve slave address from db
    t = ('1')
    cursor.execute('SELECT BusAddress FROM invertertype WHERE ID=?', t)
    slaveAddress = cursor.fetchone()[0]
    logging.info('Using slave addres "%s" from db', printHex(slaveAddress))
    if slaveAddress is None:
        print "%s : Cannot read slave address..." % (datetime.datetime.now())

    resultsBLS = {}
    resultsBLS['name'] = "BLS3000"
    resultsBLS['success'] = False
    while retries != 0:
        if serPort is None:
            logging.error("No serial port available, aborting data query...")
            retries = 0
            continue    
        rData = 0;
 
        # Inverter data ("02 04 00 0A 00 1F 91 F3")
        logging.debug("Sending inverter data request ADU")
        startRegister = "0A"
        numRegisters = "1F"
        command = mb_ReadInputRegisters(slaveAddress, startRegister, numRegisters)
        sendCommand(serPort, command)
        bytes = receiveCommand(serPort)

        rAddress, rCommand, rByteCount, rData = mb_parseResponse(bytes)
        if rData == -1: # CRC error, break here to retry command
            retries -= 1
            logging.error("CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if rData is None: # Message error, break here to stop loop
            retries -= 1
            logging.error("Message error, aborting loop; retries left: '%s'...", retries)
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
            
            if resultsBLS.has_key(name): # Some items are double words, so add the previously added item
                resultsBLS[name] = ((resultsBLS[name] * scaleFactors[name]) + int(rData[i].encode('hex') + rData[i+1].encode('hex'), 16)) / scaleFactors[name]
            else:
                resultsBLS[name] = int(rData[i].encode('hex') + rData[i+1].encode('hex'), 16) / scaleFactors[name]
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
        t=('1', str(datetime.datetime.now()), resultsBLS['VoltsPV1'], resultsBLS['VoltsPV2'], resultsBLS['CurrentPV1'], resultsBLS['CurrentPV2'], resultsBLS['VoltsAC1'], resultsBLS['VoltsAC2'], resultsBLS['VoltsAC3'], resultsBLS['CurrentAC1'], resultsBLS['CurrentAC2'], resultsBLS['CurrentAC3'], resultsBLS['FrequencyAC'], resultsBLS['PowerAC'], resultsBLS['EnergyToday'], resultsBLS['EnergyTotal'], resultsBLS['MinToday'], resultsBLS['HrsTotal'], resultsBLS['Temperature'], resultsBLS['Iac-Shift'], resultsBLS['DCI'], resultsBLS['Status1'], resultsBLS['Status2'], printHex(rData))
        logging.debug("Writing results to database: %s", t)

        cursor.execute("INSERT INTO inverterdata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
        conn.commit()
        logging.debug("Data committed to database")
        
    # while retries
    logging.info("Closing connection to serial port")
    if serPort is not None:
        serPort.close()

    # Write results to RRD db -- update using time of 'now' (N). Lifted from solget.sh
    rrdWrite = str(0) + ":" + str(0) + ":" + str(0)
    if resultsBLS['success']:
        rrdWrite = str(resultsBLS['PowerAC']) + ":" + str(resultsBLS['EnergyToday']) + ":" + str(resultsBLS['EnergyTotal'] - bls2013)
    try:
        rrdResult = subprocess.call(['rrdtool', 'update', rrdDbBLS, 'N:' + rrdWrite])
        logging.debug("Data (%s) committed to RRD database; exit code is %s", rrdWrite, rrdResult)
    except subprocess.CalledProcessError as inst:
        logging.error('Error writing data to RRD: %s', inst.args[0])

    # Soladin
    serPort = openSerial('/dev/ttyUSB1')
    if serPort is None:
        print "%s : Cannot open serial port USB1..." % (datetime.datetime.now())

    # Retrieve slave address from db
    t = ('2')
    cursor.execute('SELECT BusAddress FROM invertertype WHERE ID=?', t)
    slaveAddress = cursor.fetchone()[0]
    logging.info('Using slave addres "%s" from db', printHex(slaveAddress))
    if slaveAddress is None:
        print "%s : Cannot read slave address..." % (datetime.datetime.now())

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
        if response == -1: # CRC error, break here to retry command
            retries -= 1
            logging.error("CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if response is None: # Message error, break here to stop loop
            retries -= 1
            logging.error("Message error, aborting loop; retries left: '%s'...", retries)
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
        hTot = hexToInt(response[19:22]) / 60.0          # 19,20,21; minutes to hours
        
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
        if response2 == -1: # CRC error, break here to retry command
            retries -= 1
            logging.error("CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if response2 is None: # Message error, break here to stop loop
            retries -= 1
            logging.error("Message error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        
        mPow = hexToInt(response2[19:21]) / 1.0
        # print "MaxPow:\t" + str(mPow)

        command = mv_generateCommand(slaveAddress, sourceAddress, mvCmd_hisdat)
        sendCommand(serPort, command)
        bytes = receiveCommand(serPort)
        dest, src, response3 = mv_parseResponse(bytes, mvCmd_hisdat)
        if response3 == -1: # CRC error, break here to retry command
            retries -= 1
            logging.error("CRC error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
        if response3 is None: # Message error, break here to stop loop
            retries -= 1
            logging.error("Message error, aborting loop; retries left: '%s'...", retries)
            time.sleep(5)
            continue
 
        mTod = hexToInt(response3[0]) * 5.0 # Daily operation * 5 minutes
        wTod = hexToInt(response3[1]) / 100.0
        #print "Min today:\t" + str(mTod)
        #print "Pwr today:\t" + str(wTod)
        results2 = [statBits, uSol, iSol, fNet, uNet, wSol, wTot, tSol, hTot, "$", mPow, "$", mTod, wTod]
        logging.info("Decoded inverter data response: %s", results2)
        resultsSol['EnergyToday'] = wTod
        resultsSol['MinToday'] = mTod
        
        response = printHex(response) + " $ " + printHex(response2) + " $ " + printHex(response3)
        logging.info("Inverter data response (data): %s", printHex(response))
        # Success, so no need for retries
        retries = 0
        resultsSol['success'] = True

        conn = sqlite3.connect(sqliteDbName)
        cursor = conn.cursor()
        logging.info('Connected to SQLite database "%s"', sqliteDbName)

        t=('2', str(datetime.datetime.now()), uSol, '0.0', iSol, '0.0', uNet, '0.0', '0.0', '0.0', '0.0', '0.0', fNet, wSol, wTod, wTot, mTod, hTot, tSol, '0.0', '0.0', statBits, '0.0', response)
        logging.debug("Writing results to database: %s", t)

        cursor.execute("INSERT INTO inverterdata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
        conn.commit()
        logging.debug("Data committed to database")
    
    # while retries
    logging.info("Closing connection to serial port")
    if serPort is not None:
        serPort.close()

    # Write results to RRD db -- update using time of 'now' (N). Lifted from solget.sh
    rrdWrite = str(0) + ":" + str(0) + ":" + str(0)
    if resultsSol['success']:
        rrdWrite = str(resultsSol["PowerAC"]) + ":" +  str(resultsSol['EnergyToday']) + ":" + str(resultsSol["EnergyTotal"] - sol2013)
    try:
        rrdResult = subprocess.call(['rrdtool', 'update', rrdDbSol, 'N:' + rrdWrite])
        logging.debug("Data (%s) committed to RRD database; exit code is %s", rrdWrite, rrdResult)
    except subprocess.CalledProcessError as inst:
        logging.error('Error writing data to RRD: %s', inst.args[0])

    # Update HTML page
    createHTML(resultsBLS, resultsSol)

    # End of day checks: archive graphs
    if (hour == 23 and minute == 55):
        # Copy the file to the 'archive' directory
        logging.info("%s:%s: archiving graphs to '%s'", hour, minute, rrdArchDir)
        filenames = os.listdir(webDir)
        logging.debug("Found files: '%s'", filenames)
        try:
            for imgName in fnmatch.filter(filenames, 'solarStats*.png'):
                root, ext = os.path.splitext(imgName)
                shutil.copy(os.path.join(webDir, imgName), os.path.join(os.getcwd(), rrdArchDir, root + "_" + str(time.strftime("%Y-%m-%d")) + ext))
                logging.debug("Copying/renaming file '%s' from '%s' to '%s'", imgName, webDir, rrdArchDir)
        except IOError as inst:
            logging.error("Cannot copy/archive file '%s' from '%s' to '%s': %s", imgName, webDir, rrdArchDir, inst.args[0])
    
    # Closedown
    logging.info("Closing connection to database")
    conn.close()
    

"""
===          
BLS decoding
===
Commands
  SA =slaveAddress; FC=functionCode SR=startRegister, NR=numRegisters CR=crc
  SA FC SR SR NR NR CR CR
  02 03 00 26 00 17 E4 3C 
  FF 03 00 3C 00 01 51 D8 - busQuery
  02 04 00 00 00 03 B0 38 - serial number
  02 04 00 0A 00 1F 91 F3 - inverter data
  02 04 00 29 00 1F 60 39 
  02 04 00 2B 00 02 01 F0 - model / SW version
  02 04 00 3A 00 17 90 3A 

Holding registers (0x03)  
26	
27	
28	
29	
2A	
2B	
2C	
2D			 
2E			 
2F			 
30			 
31			 
32			 
33			 
34			 
35			 
36			 
37			 
38			 
39			 
3A			 
3B			 
3C	? Bus address	00 02

Input registers (0x04)
Reg	Description	Value
00	Serial No	42 06
01	Serial No	12 43
02	Serial No	50 30
03	?		FF FF
04	?		FF FF
05	?		FF FF
06	?		FF FF
07	?		FF FF
08	?		FF FF
09	?		FF FF
0A	VoltsPV1, 10
0B	VoltsPV2, 10
0C	CurrentPV1, 10
0D	CurrentPV2, 10
0E	VoltsAC1, 10
0F	VoltsAC2, 10
10	VoltsAC3, 10
11	CurrentAC1, 10
12	CurrentAC2, 10
13	CurrentAC3, 10
14	Frequency, 100
15	PowerAC, 10
16	PowerAC, 10
17	EnergyTodayAC, 10
18	EnergyTotalAC, 10
19	EnergyTotalAC, 10
1A	TimeToday
1B	TimeToday, 1 (min)
1C	TimeTotal, 1 
1D	TimeTotal, 1 (hr)
1E	Temperature, 10
1F	Iac-Shift, 1    01 FE
20	blank?          00 00
21	blank?          00 00
22	DCI (ma) ??
23      blank?          00 00
24      blank?          00 00
25      blank?          00 00
26      blank?          00 00
27      Status1 (0)     00 00
28	Status2, 1
29	?Pac?, 10       09 38? 
2A	?BUS?, 10       0E D8?
2B	ModelNo (10)	00 1E
2C	SWversion (100)	01 F7
2D			05 DC 
2E			00 3C 
2F			07 30 
30			06 A4 
31			00 10 
32			00 0A 
33			0A 50 
34			0A F0 
35			00 10 
36			00 0A 
37			12 8E 
38			11 94 
39			00 10 
3A			00 0A 
3B			13 9C 
3C			14 1E
3D			00 10
3E			
3F			
40			
41			
42			
43			
44			
45			
46			 
47			
48			
49			
50			
51			
52			
53			
54			
55			
56			

===          
Soladin decoding [https://github.com/teding/SolaDin]
Note: contains some errors (missing '00' in filler)
===
Commands
  DA=destAddress; SA=srcAddress FC=functionCode, CR=crc
  DA DA SA SA FC  ?  ?  ? CR
  00 00 00 00 C1 00 00 00 C1 - probe (RX: 00 00 11 00 C1 F3 00 00 C5)
  11 00 00 00 B4 00 00 00 C5 - firmware 
  11 00 00 00 B6 00 00 00 C7 - stats
  11 00 00 00 B9 00 00 00 CA    - max power
  11 00 00 00 97 01 00 00 A9 - reset max power
  11 00 00 00 9A 00 00 AB    - history (0x05 is day, where 0 is today, 9 is 9 days before
  
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
