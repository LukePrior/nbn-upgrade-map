

## Build

Build and tag a docker image for the project.  Execute from the top level directory of the project:

```shell
docker build . -f extra/docker/Dockerfile -t nbn-upgrade-map:latest
```

## Run

Create a shared network, start the DB image, then start the default processing run. Execute from the top level directory of the project:

```shell
# create a network for the containers to communicate over
docker network create test_network

# start the database
docker run -d --name db --network test_network lukeprior/nbn-upgrade-map-db:latest

# start processing (default is to identify and process a single suburb)
docker run -it -v ./results:/app/results --network test_network nbn-upgrade-map:latest ./main.py -H db -P 5432
```

## Docker Compose

You can also run everything using docker-compose. Execute from the top level directory of the project:

```
❯ docker-compose -f extra/docker/docker-compose.yaml --profile test up
[+] Running 2/2
 ✔ Container docker-db-1   Created                                                                                                                                                                                               0.0s
 ✔ Container docker-app-1  Recreated                                                                                                                                                                                             0.2s
Attaching to docker-app-1, docker-db-1
docker-db-1   | 2023-09-15 05:26:23.066 UTC [1] LOG:  starting PostgreSQL 15.4 (Debian 15.4-1.pgdg100+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 8.3.0-6) 8.3.0, 64-bit
docker-db-1   | 2023-09-15 05:26:23.068 UTC [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
docker-db-1   | 2023-09-15 05:26:23.068 UTC [1] LOG:  listening on IPv6 address "::", port 5432
docker-db-1   | 2023-09-15 05:26:23.077 UTC [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
docker-db-1   | 2023-09-15 05:26:23.168 UTC [9] LOG:  database system was shut down at 2023-09-15 05:25:24 UTC
docker-db-1   | 2023-09-15 05:26:23.181 UTC [1] LOG:  database system is ready to accept connections
docker-app-1  | 2023-09-15 05:26:23,747 INFO MainThread Checking for externally updated geojson results...
docker-app-1  | 2023-09-15 05:27:43,659 INFO MainThread ...done
docker-app-1  | 2023-09-15 05:27:43,928 INFO MainThread Creating DB index...
docker-app-1  | 2023-09-15 05:27:44,128 INFO MainThread Checking for unprocessed suburbs...
docker-app-1  | 2023-09-15 05:27:44,128 INFO MainThread Checking for announced suburbs that haven't been updated in 21 days...
docker-app-1  | 2023-09-15 05:27:44,130 INFO MainThread Checking for all suburbs...
docker-app-1  | 2023-09-15 05:27:44,139 INFO MainThread Processing Southern Cross, VIC
docker-app-1  | 2023-09-15 05:27:44,139 INFO MainThread Fetching all addresses for Southern Cross, VIC
docker-app-1  | 2023-09-15 05:27:44,210 INFO MainThread Fetched 53 addresses from database
docker-app-1  | 2023-09-15 05:27:44,214 INFO MainThread Loaded 52 addresses from output file
docker-app-1  | 2023-09-15 05:27:44,214 INFO MainThread Submitting 53 requests to add NBNco data...
docker-app-1  | 2023-09-15 05:28:08,064 INFO nbn_0 Completed 53 requests
docker-app-1  | 2023-09-15 05:28:08,075 INFO MainThread Completed. Tally of tech types: {'WIRELESS': 53}
docker-app-1  | 2023-09-15 05:28:08,075 INFO MainThread Location ID types: {'LOC': 47, 'Other': 6}
docker-app-1  | 2023-09-15 05:28:08,077 INFO MainThread Writing results to results/VIC/southern-cross.geojson
docker-app-1  | 2023-09-15 05:28:09,832 INFO MainThread Updating progress.json
docker-app-1 exited with code 0
```