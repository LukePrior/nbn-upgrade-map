# STAGE 1: import the DB dump files then export a cutdown CSV file
FROM postgis/postgis:16-3.4-alpine as import
ENV POSTGRES_HOST_AUTH_METHOD=trust

RUN mkdir -p /data
WORKDIR /data

ARG GNAF_LOADER_TAG="latest"
ADD gnaf-${GNAF_LOADER_TAG}.dmp .

ADD 20_import_gnaf.sh /docker-entrypoint-initdb.d/20_import_gnaf.sh

# need postgres to exit after running the script, so we can run the next script
RUN sed -i 's/exec "$@"/#exec "$@"/' /usr/local/bin/docker-entrypoint.sh
RUN bash -x /usr/local/bin/docker-entrypoint.sh postgres


# STAGE 2: load the CSV file from previous stage into right DB version (no PostGIS)
FROM postgres:16-alpine as load
ENV POSTGRES_HOST_AUTH_METHOD=trust

RUN mkdir -p /data
WORKDIR /data
COPY --from=import --chown=postgres /tmp/address_principals.csv.gz /data/
ADD --chown=postgres create-table.sql /data/
ADD 20_import_csv.sh /docker-entrypoint-initdb.d/

# need postgres to exit after running the script, so we can run the next script
RUN sed -i 's/exec "$@"/#exec "$@"/' /usr/local/bin/docker-entrypoint.sh
RUN bash -x /usr/local/bin/docker-entrypoint.sh postgres


# STAGE 3: just use the data from the previous stage
FROM postgres:16-alpine as final
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=password

COPY --from=load --chown=postgres /var/lib/postgresql/data /var/lib/postgresql/data
