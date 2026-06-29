# WMATA Better Bus Network Redesign Analysis — README

This README documents the data inputs, processing pipeline, and output files produced for an analysis of WMATA's 2025 Better Bus Network Redesign.

## Data Inputs

There are four data inputs used in the script. See the table below for details.

| Data | Source | Description |
|---|---|---|
| General Transit Feed Specification (GTFS) | [Mobility Database](https://mobilitydatabase.org/feeds/gtfs/mdb-1846) | Data analyzed ranges from 12/15/2024 through 12/19/2025, resulting in 6 months of pre-redesign data and 6 months of post-redesign data. |
| Route Crosswalk | [2025 DC Route Profiles from WMATA](https://www.wmata.com/initiatives/plans/Better-Bus/upload/Resource_2025-Route-Profiles_District-of-Columbia.pdf) | Used to determine route pairs before and after the redesign. The crosswalk matches pairs based on any similarity between two routes, so some manual processing is needed to remove extraneous pairs. For example, the D60 and the D6X both pair with the old S2 and S9, rather than the two local routes (D60 and S2) pairing together and the two limited-stop routes (D6X and S9) pairing together. |
| Corridor Crosswalk | Manual Review | A corridor is defined as a set of overlapping routes, determined by manual review. |
| Ridership Data | [Metro Bus Ridership Summary](https://www.wmata.com/initiatives/ridership-portal/Metrobus-Ridership-Summary.cfm) | Not used in the GGWash article, but processed in code. |

## Processing Pipeline

GTFS data was analyzed using the `gtfs_kit` Python package. In the script, the GTFS feeds and the route and corridor crosswalks are loaded to establish pre/post route pairs and corridor groupings. Metrics are then computed and matched across those pairs:

- Ridership by day type
- Stop counts
- Stop spacing per trip
- Service-pattern statistics (headway, span, speed, and trip counts)

The final output of the script can be seen in the formatted Excel file attached in the git repository. That final output is one row per route pair/metric and serves as input to the chart figures in the article.

## Usage Notes

- The script can be run at the **corridor** or **route** level, though some statistics (e.g., headway) are currently implemented only at the route level.
- It can also be run across **weekdays** or **weekends**, though cited results only reference weekday output.
- A processed GTFS data build is exported to `/intermediate`.
- The final output in `/export` only includes routes/corridors with a matched pre and post counterpart — anything dropped or newly added with no match falls out of the analysis.
