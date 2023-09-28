To create sample data in SQLite use the following process:

- create empty DB per process described  in DB:

```
sqlite3 tests/data/sample-addresses.db

-- create table and index per process described in DB
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

-- attach and import a subset of the data
attach database './extra/db/address_principals.db' as full_db;
INSERT INTO main.address_principals SELECT * FROM full_db.address_principals WHERE locality_name like '%SOMER%' ORDER BY RANDOM() LIMIT 100;
```

