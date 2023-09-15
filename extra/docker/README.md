

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
