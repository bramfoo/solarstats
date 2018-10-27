import os
import sys
import uuid
import logging

from flask import jsonify, request, url_for
from uptime import boottime, uptime
from datetime import datetime, timedelta
from solarstats import app

API_VERSION = '0.1'
LOG_FORMAT = '%(asctime)-15s %(message)s'
STRFTIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)

database = None


def setup(solarDb):
    global database
    database = solarDb
    logging.debug('Using db "%s"', solarDb)


@app.route('/', methods=['GET', 'POST', 'DELETE'])
def index():
    logging.debug(str(request.method) + " on " + str(request.path))
    if request.method == 'GET':
        response = "version 0.1"
        logging.debug(response)
        return jsonify(response)

    if request.method == 'POST':
        req_data = request.get_json()
        logging.debug("POST data: " + str(req_data))

    else:
        logging.debug(request.method + str(request))
        # Returning empty response
        return ('', 204)

@app.route('/readings/', methods=["GET"])
@app.route('/readings/<int:inverterID>', methods=["GET"])
def lastday(inverterID=None):
    logging.debug(str(request.method) + " on " + str(request.path))
    if request.method == 'GET':
        if inverterID is None:
            response = database.inverterInfo()
        else:
            fromDate = request.args.get('from', default = None, type = int)
            toDate = request.args.get('to', default = None, type = str)
            response = database.reading(str(inverterID))
        logging.debug(response)
        return jsonify(response)
    else:
        return ('', 204)

@app.route('/max', methods=["GET"])
def max():
    logging.debug(str(request.method) + " on " + str(request.path))
    if request.method == 'GET':
      response = "select max(datetime) from inverterdata where CurrentPV1 <> 0"
      logging.debug(response)
      return jsonify(response)
    else:
        return ('', 204)


@app.route('/status', methods=["GET"])
def status():
    logging.debug(str(request.method) + " on " + str(request.path))
    if request.method == 'GET':

        # Uptime & boottime
        timeUp = timedelta(seconds=uptime())
        timeBoot = boottime()
        logging.debug('Boottime: %s; uptime: %s days, %s seconds',
                      timeBoot, timeUp.days, timeUp.seconds)
        osInfo = {'boottime': timeBoot.strftime(
            STRFTIME_FORMAT), 'uptime': "{}".format(timeUp)}

        # Port info
        usb0 = os.path.exists('/dev/ttyUSB0')
        usb1 = os.path.exists('/dev/ttyUSB1')
        ports = {'USB0': usb0, 'USB1': usb1}

        # Database info
        dbStatus = database.status()
        dbInfo = {'version': dbStatus[0], 'name': dbStatus[1],
                  'inverters': database.inverterInfo()}
        for id in dbInfo['inverters']:
           dbInfo['inverters'][id]['latestReading'] = database.latestReading(id)

        response = {'API version': API_VERSION,
                    'ports': ports, 'OS': osInfo, 'database': dbInfo}
        logging.debug(response)
        return jsonify(response)
    else:
        return ('', 204)
