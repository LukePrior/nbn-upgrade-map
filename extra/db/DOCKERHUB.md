# NBN Upgrade Map - GNAF Database

This is a cut-down version of the [minus34/gnaf-loader](https://github.com/minus34/gnaf-loader) PostgreSQL database containing the Geocoded National Address File of Australia (GNAF).

## What is this?

The [NBN FTTP Upgrade Map](https://github.com/LukePrior/nbn-upgrade-map) project uses this database to check which Australian premises are eligible for NBN Fibre to the Premises (FTTP) upgrades. This Docker image contains just the address data needed for the project, making it much smaller and faster to use.

**Size comparison:**
- Original gnaf-loader image: **32GB**
- This cut-down image: **3.73GB**

## Quick Start

Pull and run the database:

```bash
docker run -p 5433:5432 lukeprior/nbn-upgrade-map-db:latest
```

The database will be available at:
- **Host:** localhost
- **Port:** 5433
- **Username:** postgres
- **Password:** password
- **Database:** geo

## What's Inside?

The database contains a single table `address_principals` with the following columns:

- `gnaf_pid` - Unique address identifier
- `address` - Full street address
- `locality_name` - Suburb/town name
- `postcode` - Australian postcode
- `state` - Australian state/territory
- `latitude` - Geographic latitude
- `longitude` - Geographic longitude

The table includes **15.4 million Australian addresses** and has an index on `(locality_name, state)` for fast lookups.

## Usage Example

Connect to the database and query addresses:

```sql
SELECT * FROM address_principals 
WHERE locality_name = 'SYDNEY' 
AND state = 'NSW' 
LIMIT 10;
```

## Use Cases

This database is perfect for:
- Looking up Australian addresses by suburb/locality
- Geocoding Australian addresses
- NBN availability checking
- Australian address validation
- Geographic analysis of Australian locations

## Building from Source

The image is built from the [nbn-upgrade-map repository](https://github.com/LukePrior/nbn-upgrade-map) using a multi-stage Docker build that:

1. Downloads the latest GNAF data from [minus34.com](https://minus34.com/opendata/)
2. Imports only the required address table
3. Exports a compressed CSV with just the needed columns
4. Creates a fresh PostgreSQL database with the optimized data

## Data Source

The address data comes from the [Geocoded National Address File (GNAF)](https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf), an authoritative dataset of Australian addresses maintained by the Australian government. The GNAF dataset is updated quarterly with new releases, and this Docker image is rebuilt to include the latest data when new versions are available.

## Related Projects

- [NBN FTTP Upgrade Map](https://nbn.lukeprior.com) - Interactive map showing NBN FTTP upgrade eligibility
- [GitHub Repository](https://github.com/LukePrior/nbn-upgrade-map) - Source code for the NBN upgrade checker
- [minus34/gnaf-loader](https://github.com/minus34/gnaf-loader) - Original full GNAF database image

## Tags

- `latest` - Latest version of the database
- `<version>` - Specific GNAF data version (e.g., `202411`)

## Support

For issues or questions:
- [Open an issue](https://github.com/LukePrior/nbn-upgrade-map/issues) on GitHub
- Check the [project README](https://github.com/LukePrior/nbn-upgrade-map/blob/main/README.md)

## License

The GNAF data is provided under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).
