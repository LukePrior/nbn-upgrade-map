CREATE TABLE gnaf_cutdown.address_principals
(
  gnaf_pid text NOT NULL,
  address text NOT NULL,
  locality_name text NOT NULL,
  postcode SMALLINT NULL,
  state text NOT NULL,
  latitude numeric(10,8) NOT NULL,
  longitude numeric(11,8) NOT NULL
);

ALTER TABLE gnaf_cutdown.address_principals OWNER TO postgres;

CREATE index address_name_state on gnaf_cutdown.address_principals (locality_name, state);
