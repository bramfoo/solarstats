from flask import Flask
from flask_cors import CORS
import logging
import json     # Config
import sqlite3  # Database connection
import datetime

app = Flask(__name__)
CORS(app, resources=r'/*', allow_headers="Content-Type")

import solarstats.solarAPI
from solarstats.solarDB import SolarDB

# Read config
with open('config.json', 'r') as f:
  config = json.load(f)

sqliteDb = config['database']['filename'] 
db = SolarDB(sqliteDb)
solarstats.solarAPI.setup(db)