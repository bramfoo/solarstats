-- Run the following to initialise the database:
-- sqlite3 SolarElz673.sqlt < SolarElz673.sql

CREATE TABLE IF NOT EXISTS inverter (
  ID INTEGER(8) PRIMARY KEY NOT NULL,
  SerialNumber TEXT NOT NULL,
  InverterType_ID TEXT NOT NULL,
  UNIQUE (SerialNumber, InverterType_ID),
  FOREIGN KEY (InverterType_ID) REFERENCES invertertype(ID) ON DELETE SET NULL
  );

CREATE TABLE IF NOT EXISTS invertertype (
  ID INTEGER(8) PRIMARY KEY NOT NULL,
  Manufacturer TEXT NOT NULL,
  Model TEXT NOT NULL,
  BusAddress TEXT,
  SWversion TEXT,
  MaxOutput INTEGER(8) DEFAULT NULL,
  UNIQUE (Manufacturer, Model)
);

CREATE TABLE IF NOT EXISTS inverterdata (
  Inverter_ID INTEGER(8) NOT NULL,
  DateTime TEXT NOT NULL,
  VoltsPV1 REAL,
  VoltsPV2 REAL,
  CurrentPV1 REAL,
  CurrentPV2 REAL,
  VoltsAC1 REAL,
  VoltsAC2 REAL,
  VoltsAC3 REAL,
  CurrentAC1 REAL,
  CurrentAC2 REAL,
  CurrentAC3 REAL,
  FrequencyAC REAL,
  PowerAC REAL,
  EnergyToday REAL,
  EnergyTotal REAL,
  MinToday INTEGER(8),
  HrsTotal INTEGER(8),
  Temperature REAL,
  Iac_Shift REAL,
  DCI REAL,
  Status1 INTEGER(8),
  Status2 INTEGER(8),
  RawData TEXT NOT NULL,
  UNIQUE (Inverter_ID, DateTime)
  FOREIGN KEY (Inverter_ID) REFERENCES inverter(ID)
);

CREATE TABLE IF NOT EXISTS outputhistory (
  Inverter_Id  INTEGER(8) PRIMARY KEY NOT NULL,
  DateTime TEXT NOT NULL,
  OutputKwh REAL NOT NULL,
  Duration INTEGER(8) NOT NULL,
  MinPower REAL,
  MaxPower REAL,
  UNIQUE (Inverter_Id, DateTime),
  FOREIGN KEY (Inverter_ID) REFERENCES inverter(ID)
);

