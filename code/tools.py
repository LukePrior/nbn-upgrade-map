import psycopg2
import json

conn = psycopg2.connect(database="postgres", host="localhost", user="postgres", password="password", port="5433")

cur = conn.cursor()

cur.execute("SELECT DISTINCT locality_name, state FROM gnaf_202302.address_principals")

rows = cur.fetchall()

suburbs = {"states": {"NSW": [], "VIC": [], "QLD": [], "SA": [], "WA": [], "TAS": [], "NT": [], "ACT": []}}

act = []
act_suburbs = open("results/misc/ACT.txt", "r")
for line in act_suburbs:
    act.append(line.strip().upper())

nt = []
nt_suburbs = open("results/misc/NT.txt", "r")
for line in nt_suburbs:
    nt.append(line.strip().upper())

tas = []
tas_suburbs = open("results/misc/TAS.txt", "r")
for line in tas_suburbs:
    tas.append(line.strip().upper())

wa = []
wa_suburbs = open("results/misc/WA.txt", "r")
for line in wa_suburbs:
    wa.append(line.strip().upper())

sa = []
sa_suburbs = open("results/misc/SA.txt", "r")
for line in sa_suburbs:
    sa.append(line.strip().upper())

qld = []
qld_suburbs = open("results/misc/QLD.txt", "r")
for line in qld_suburbs:
    qld.append(line.strip().upper())

vic = []
vic_suburbs = open("results/misc/VIC.txt", "r")
for line in vic_suburbs:
    vic.append(line.strip().upper())

nsw = []
nsw_suburbs = open("results/misc/NSW.txt", "r")
for line in nsw_suburbs:
    nsw.append(line.strip().upper())

for row in rows:
    if row[1] in suburbs["states"] and row[0] not in suburbs["states"][row[1]]:
        if row[1] == "ACT" and row[0] not in act:
            continue
        if row[1] == "NT" and row[0] not in nt:
            continue
        if row[1] == "TAS" and row[0] not in tas:
            continue
        if row[1] == "WA" and row[0] not in wa:
            continue
        if row[1] == "SA" and row[0] not in sa:
            continue
        if row[1] == "QLD" and row[0] not in qld:
            continue
        if row[1] == "VIC" and row[0] not in vic:
            continue
        if row[1] == "NSW" and row[0] not in nsw:
            continue
        suburbs["states"][row[1]].append(row[0])

with open("results/suburbs.json", "w") as outfile:
    json.dump(suburbs, outfile, indent=4)
