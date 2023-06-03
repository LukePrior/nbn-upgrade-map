########################################################################
# data-extraction stage
FROM debian:buster-slim

# Postgres user password - WARNING: change this to something a lot more secure
ARG pg_password="password"
ENV PGPASSWORD=${pg_password}

# get postgres signing key, add Postgres repo to apt and install Postgres with PostGIS
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y sudo wget gnupg2 \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add - \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ buster-pgdg main" | sudo tee  /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y postgresql-15 postgresql-client-15 postgis postgresql-15-postgis-3 \
    && apt-get autoremove -y --purge \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# start Postgres server and set the default user password
RUN /etc/init.d/postgresql start \
    && sudo -u postgres psql -c "ALTER USER postgres PASSWORD '${pg_password}';" \
    && sudo -u postgres psql -c "CREATE EXTENSION postgis;" \
    && /etc/init.d/postgresql stop

# enable external access to postgres - WARNING: these are insecure settings! Edit these to restrict access
RUN echo "host all  all    0.0.0.0/0  md5" >> /etc/postgresql/15/main/pg_hba.conf
RUN echo "listen_addresses='*'" >> /etc/postgresql/15/main/postgresql.conf

# download and restore GNAF & Admin Boundary Postgres dump files
RUN mkdir -p /data
WORKDIR /data

ARG GNAF_LOADER_TAG="latest"

ADD gnaf-${GNAF_LOADER_TAG}.dmp .

RUN /etc/init.d/postgresql start \
    && pg_restore -v -Fc -d postgres -h localhost -p 5432 -U postgres --schema-only /data/gnaf-$GNAF_LOADER_TAG.dmp \
    && pg_restore -v -Fc -d postgres -h localhost -p 5432 -U postgres --data-only -t address_principals --disable-triggers /data/gnaf-$GNAF_LOADER_TAG.dmp \
    && /etc/init.d/postgresql stop \
    && rm /data/gnaf-$GNAF_LOADER_TAG.dmp

EXPOSE 5432

# set user for postgres startup
USER postgres

RUN /etc/init.d/postgresql start \
    && psql -c "copy (SELECT gnaf_pid, address, locality_name, postcode, state, latitude, longitude FROM gnaf_${GNAF_LOADER_TAG}.address_principals) to stdout with CSV HEADER;" | gzip -9 > /tmp/address_principals.csv.gz \
    && /etc/init.d/postgresql stop

# Start postgres when starting the container
CMD ["/usr/lib/postgresql/15/bin/postgres", "-D", "/var/lib/postgresql/15/main", "-c", "config_file=/etc/postgresql/15/main/postgresql.conf"]


########################################################################
# minimal DB stage

FROM debian:buster-slim

# Postgres user password - WARNING: change this to something a lot more secure
ARG pg_password="password"
ENV PGPASSWORD=${pg_password}

# get postgres signing key, add Postgres repo to apt and install Postgres with PostGIS
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y sudo wget gnupg2 \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add - \
    && echo "deb http://apt.postgresql.org/pub/repos/apt/ buster-pgdg main" | sudo tee  /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y postgresql-15 postgresql-client-15 postgis postgresql-15-postgis-3 \
    && apt-get autoremove -y --purge \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# start Postgres server and set the default user password
RUN /etc/init.d/postgresql start \
    && sudo -u postgres psql -c "ALTER USER postgres PASSWORD '${pg_password}';" \
    && sudo -u postgres psql -c "CREATE EXTENSION postgis;" \
    && /etc/init.d/postgresql stop

# enable external access to postgres - WARNING: these are insecure settings! Edit these to restrict access
RUN echo "host all  all    0.0.0.0/0  md5" >> /etc/postgresql/15/main/pg_hba.conf
RUN echo "listen_addresses='*'" >> /etc/postgresql/15/main/postgresql.conf

# download and restore SQL schema and previously exported table data
RUN mkdir -m a+w -p /data
WORKDIR /data

EXPOSE 5432

ADD --chown=postgres create-table.sql /data/
COPY --from=0 --chown=postgres /tmp/address_principals.csv.gz /data/

# set user for postgres startup
USER postgres

RUN /etc/init.d/postgresql start \
    && psql -a -c "CREATE SCHEMA gnaf_cutdown" \
    && psql -a -f create-table.sql \
    && gunzip -c address_principals.csv.gz | psql -c 'COPY gnaf_cutdown.address_principals FROM stdin WITH CSV HEADER' \
    && /etc/init.d/postgresql stop \
    && rm -v create-table.sql address_principals.csv.gz

# Start postgres when starting the container
CMD ["/usr/lib/postgresql/15/bin/postgres", "-D", "/var/lib/postgresql/15/main", "-c", "config_file=/etc/postgresql/15/main/postgresql.conf"]
