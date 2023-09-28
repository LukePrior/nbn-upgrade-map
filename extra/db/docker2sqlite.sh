#!/bin/bash

set -ex

# Extract CSV from the DB if we don't have it already.
# It's also available as part of the docker-build process, but this is a bit more flexible.
CSV_FILENAME=address_principals.csv
if [ -f $CSV_FILENAME ]; then
  echo "CSV file already exists, skipping extract..."
else
  docker run -d --name db --publish=5433:5432 lukeprior/nbn-upgrade-map-db:latest
  sleep 5  # it takes a few seconds to be ready
  psql -h localhost -p 5433 -U postgres -c 'COPY gnaf_cutdown.address_principals TO stdout WITH CSV HEADER' > $CSV_FILENAME
  docker rm -f db
fi

# Create a new sqlite DB with the contents of the CSV
DB_FILENAME=address_principals.sqlite
if [ -f $DB_FILENAME ]; then
  echo "SQLite file $DB_FILENAME already exists, skipping creation..."
else
  sqlite3 $DB_FILENAME <<EOF

  CREATE TABLE address_principals
  (
    gnaf_pid text NOT NULL,
    address text NOT NULL,
    locality_name text NOT NULL,
    postcode INTEGER NULL,
    state text NOT NULL,
    latitude numeric(10,8) NOT NULL,
    longitude numeric(11,8) NOT NULL
  );

  CREATE INDEX address_name_state ON address_principals(locality_name, state);

.mode csv
.import $CSV_FILENAME address_principals
.exit
EOF

fi
