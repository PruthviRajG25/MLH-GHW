import argparse
import os
import random
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import execute_values


def connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "sensor_dashboard"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )


def build_rows(days: int, sensors: int, interval_minutes: int):
    random.seed(42)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    first = now - timedelta(days=days)
    rows = []
    point_count = (days * 24 * 60) // interval_minutes
    for point in range(point_count):
        timestamp = first + timedelta(minutes=point * interval_minutes)
        for sensor_number in range(1, sensors + 1):
            daily_cycle = 3 * __import__("math").sin(timestamp.hour / 24 * 2 * __import__("math").pi)
            temperature = 21 + daily_cycle + sensor_number * 0.4 + random.gauss(0, 0.7)
            humidity = 58 - daily_cycle * 1.8 - sensor_number + random.gauss(0, 2.0)
            rows.append((timestamp, f"sensor-{sensor_number:02d}", round(temperature, 2), round(max(0, min(100, humidity)), 2)))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Load deterministic sample readings.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--sensors", type=int, default=4)
    parser.add_argument("--interval-minutes", type=int, default=5)
    args = parser.parse_args()
    if min(args.days, args.sensors, args.interval_minutes) <= 0:
        parser.error("days, sensors, and interval-minutes must be positive")

    rows = build_rows(args.days, args.sensors, args.interval_minutes)
    with connection() as database, database.cursor() as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO sensor_data (recorded_at, sensor_id, temperature, humidity)
            VALUES %s
            ON CONFLICT (recorded_at, sensor_id) DO NOTHING
            """,
            rows,
            page_size=5000,
        )
        cursor.execute(
            "CALL refresh_continuous_aggregate('hourly_sensor_metrics', NULL, NOW())"
        )
    print(f"Prepared {len(rows):,} deterministic readings; duplicates were skipped.")


if __name__ == "__main__":
    main()
