import logging

import psycopg2
from psycopg2.extras import NamedTupleCursor


class AddressDB:
    """Connect to the GNAF PostgreSQL database and query for addresses. See https://github.com/minus34/gnaf-loader"""

    def __init__(self, database: str, host: str, port: str, user: str, password: str, create_index: bool = True):
        """Connect to the database"""
        self.conn = psycopg2.connect(
            database=database, host=host, port=port, user=user, password=password, cursor_factory=NamedTupleCursor
        )

        self.cur = self.conn.cursor()

        # detect the schema used by the DB
        self.cur.execute("SELECT schema_name FROM information_schema.schemata where schema_name like 'gnaf_%'")
        self.db_schema = self.cur.fetchone().schema_name

        # optionally create a DB index
        if create_index:
            try:
                logging.info("Creating DB index...")
                self.cur.execute(
                    f"CREATE index address_name_state on {self.db_schema}.address_principals (locality_name, state)"
                )
                self.conn.commit()
            except psycopg2.errors.DuplicateTable:
                logging.info("Skipping index creation as already exists")
                self.conn.rollback()

    def get_addresses(self, target_suburb: str, target_state: str) -> list:
        """Return a list of addresses for the provided suburb+state from the database."""
        query = f"""
            SELECT gnaf_pid, address, locality_name, postcode, latitude, longitude
            FROM {self.db_schema}.address_principals
            WHERE locality_name = '{target_suburb}' AND state = '{target_state}'
            LIMIT 100000"""

        self.cur.execute(query)

        addresses = []
        row = self.cur.fetchone()
        while row is not None:
            address = {
                "gnaf_pid": row.gnaf_pid,
                "name": f"{row.address} {row.locality_name} {row.postcode}",
                "location": [float(row.longitude), float(row.latitude)],
            }
            addresses.append(address)
            row = self.cur.fetchone()

        return addresses
