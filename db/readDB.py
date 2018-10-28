# Reads information from the database and outputs it in JSON format
# Usage: python readDB.py > bls3000.json
# 
# SQLite code taken from http://zetcode.com/db/sqlitepythontutorial/
# JSON info from https://docs.python.org/2/library/json.html
import sqlite3 as lite
import json

# open existing database
conn = lite.connect('SolarElz673.sqlt')

with conn:
    #conn.row_factory = lite.Row
    cur = conn.cursor()
    t = (1,)
    cur.execute(
        'SELECT * FROM inverterdata WHERE Inverter_ID=? ORDER BY DateTime', t)

    col_names = [cn[0] for cn in cur.description]

    rows = cur.fetchall()

    for row in rows:
        print(json.dumps(
            {"index": {"_index": "solar-bls3000", "_type": "reading"}}))
        print(json.dumps({"timestamp": str(row[1]), col_names[14]: row[14], col_names[15]
              : row[15], col_names[16]: row[16], col_names[17]: row[17], col_names[23]: row[23]}))
        # Pretty print
        #print(json.dumps({col_names[0]+'_'+str(row[0]) : [{ row[1]: [{col_names[14]: row[14], col_names[16]: row[16]}]}]}, sort_keys=True, indent=2, separators=(',', ': ')))

# close connection
conn.close()