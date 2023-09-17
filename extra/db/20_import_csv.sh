#!/bin/bash

set -x

psql -a -c "CREATE SCHEMA gnaf_cutdown"

psql -a -f /data/create-table.sql

gunzip -c /data/address_principals.csv.gz | psql -c 'COPY gnaf_cutdown.address_principals FROM stdin WITH CSV HEADER'


