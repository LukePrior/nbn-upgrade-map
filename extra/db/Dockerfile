ARG GNAF_LOADER_TAG="latest"

FROM minus34/gnafloader:${GNAF_LOADER_TAG}
WORKDIR /data
USER postgres
RUN /usr/lib/postgresql/15/bin/pg_ctl start -D /var/lib/postgresql/15/main -o '-c config_file=/etc/postgresql/15/main/postgresql.conf' \
  && sleep 5 \
  && psql -c "copy (SELECT gnaf_pid, address, locality_name, postcode, state, latitude, longitude FROM gnaf_202305.address_principals) to stdout with CSV HEADER;" | gzip -9 > /tmp/address_principals.csv.gz


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

# # Add VOLUMEs to allow backup of config, logs and databases
# VOLUME  ["/etc/postgresql", "/var/log/postgresql", "/var/lib/postgresql"]

# Start postgres when starting the container
CMD ["/usr/lib/postgresql/15/bin/postgres", "-D", "/var/lib/postgresql/15/main", "-c", "config_file=/etc/postgresql/15/main/postgresql.conf"]
