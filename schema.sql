-- TimescaleDB 2.x schema for the Accelerate Dashboards demo.
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sensor_data (
    recorded_at TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    temperature DOUBLE PRECISION NOT NULL CHECK (temperature BETWEEN -80 AND 100),
    humidity DOUBLE PRECISION NOT NULL CHECK (humidity BETWEEN 0 AND 100),
    PRIMARY KEY (recorded_at, sensor_id)
);

SELECT create_hypertable('sensor_data', 'recorded_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS sensor_data_sensor_time_idx
    ON sensor_data (sensor_id, recorded_at DESC);

DROP MATERIALIZED VIEW IF EXISTS hourly_sensor_metrics;

CREATE MATERIALIZED VIEW hourly_sensor_metrics
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', recorded_at) AS bucket,
    sensor_id,
    AVG(temperature) AS avg_temperature,
    AVG(humidity) AS avg_humidity,
    MIN(temperature) AS min_temperature,
    MAX(temperature) AS max_temperature,
    COUNT(*)::BIGINT AS reading_count
FROM sensor_data
GROUP BY bucket, sensor_id
WITH NO DATA;

-- Real-time aggregation appends recent raw rows to materialized buckets.
-- This setting is available in TimescaleDB 2.x; omit it on older releases.
ALTER MATERIALIZED VIEW hourly_sensor_metrics
    SET (timescaledb.materialized_only = false);

SELECT add_continuous_aggregate_policy(
    'hourly_sensor_metrics',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE
);
