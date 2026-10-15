# Accelerate Dashboards with Continuous Aggregates Using TimescaleDB

Pulseboard is a Flask dashboard for sensor time-series data. It stores raw readings in a TimescaleDB hypertable and uses a continuous aggregate (CAGG) to pre-compute hourly temperature and humidity metrics.

## What this demonstrates

TimescaleDB is a PostgreSQL extension for time-series workloads. A hypertable automatically partitions time-series rows into time-based chunks while retaining PostgreSQL's SQL interface.

`hourly_sensor_metrics` is a continuous aggregate: a materialized view maintained incrementally by TimescaleDB. Instead of scanning every raw reading each time the dashboard loads, the hourly API reads pre-computed averages, minimums, maximums, and counts. Raw queries are still useful when you need individual readings or ad-hoc calculations; CAGG queries are the better fit for repeated dashboard summaries.

The schema sets `timescaledb.materialized_only = false`, enabling real-time aggregation on TimescaleDB versions that support it. The query combines the materialized portion with recent raw rows that have not yet been materialized. On older versions, remove that `ALTER MATERIALIZED VIEW` statement and use a materialized-only CAGG.

## Requirements

- PostgreSQL >= 14
- TimescaleDB 2.x installed and enabled for the PostgreSQL instance
- Python 3.10+

## Install and run

Create a database and install the Python dependencies:

```bash
createdb sensor_dashboard
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Set connection variables if your local PostgreSQL credentials differ:

```bash
# Windows PowerShell
$env:PGHOST="localhost"; $env:PGPORT="5432"
$env:PGDATABASE="sensor_dashboard"; $env:PGUSER="postgres"; $env:PGPASSWORD="postgres"
```

Install the hypertable, CAGG, and refresh policy:

```bash
psql -d sensor_dashboard -f schema.sql
python seed_data.py --days 30 --sensors 4 --interval-minutes 5
python app.py
```

Open http://127.0.0.1:5000. The seed script is deterministic and uses `ON CONFLICT DO NOTHING`, so it is safe to run again. The default data set contains 30 days of readings for four sensors at five-minute intervals.

## Refresh policy and real-time data

The policy refreshes the last 30 days while leaving the newest hour for real-time aggregation. TimescaleDB's background worker runs the policy every 15 minutes. For an immediate refresh after loading data, run:

```sql
CALL refresh_continuous_aggregate('hourly_sensor_metrics', NULL, NOW());
```

Check policy status with:

```sql
SELECT * FROM timescaledb_information.continuous_aggregates;
SELECT * FROM timescaledb_information.jobs
WHERE proc_name = 'policy_refresh_continuous_aggregate';
```

## API endpoints

- `GET /api/metrics?start=2026-01-01&end=2026-02-01` returns summary metrics from the CAGG.
- `GET /api/hourly?...` returns hourly rows for charts.
- `GET /api/sensors?...` returns raw hypertable sensor statistics.
- `GET /api/performance?...` runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for equivalent raw and CAGG queries. The dashboard displays the database-reported execution times and row counts; it never fabricates benchmark results.

All values from query parameters are passed as psycopg2 parameters rather than interpolated into SQL. Invalid date ranges and database errors are returned as JSON error responses.

## Troubleshooting

**`extension "timescaledb" is not available`:** install the TimescaleDB package matching your PostgreSQL major version, add `timescaledb` to `shared_preload_libraries` as instructed by the installer, restart PostgreSQL, and retry `CREATE EXTENSION`.

**`relation "hourly_sensor_metrics" does not exist`:** run `psql -d sensor_dashboard -f schema.sql` before starting Flask.

**The dashboard has no rows:** confirm `python seed_data.py` succeeded, select a date range containing the generated data, and refresh the CAGG with the `CALL` statement above.

**`materialized_only` is not recognized:** your TimescaleDB release may not support real-time aggregates. Remove that setting from `schema.sql`; the CAGG remains usable, but the latest unmaterialized rows will not be included until a refresh.

## Upload to GitHub

```bash
git init
git add .
git commit -m "Build TimescaleDB continuous aggregate dashboard"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Do not commit `.env`, database passwords, or production credentials. Use repository secrets and environment variables for deployment.
