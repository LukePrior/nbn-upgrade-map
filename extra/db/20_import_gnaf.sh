#!/bin/bash

set -x

pg_restore -v -Fc -d postgres --schema-only /data/gnaf-$GNAF_LOADER_TAG.dmp

pg_restore -v -Fc -d postgres --data-only -t address_principals --disable-triggers /data/gnaf-$GNAF_LOADER_TAG.dmp

psql -c "copy (SELECT gnaf_pid, address, locality_name, postcode, state, latitude, longitude FROM gnaf_${GNAF_LOADER_TAG}.address_principals) to stdout with CSV HEADER;" | gzip -9 > /tmp/address_principals.csv.gz

echo "Exported CSV..."
ls -l /tmp/address_principals.csv.gz
