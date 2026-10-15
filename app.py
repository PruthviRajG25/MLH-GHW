import os
import time
from datetime import date, datetime, timedelta
from typing import Any

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)


def database_config() -> dict[str, Any]:
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "sensor_dashboard"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", "postgres"),
    }


def get_connection():
    return psycopg2.connect(**database_config())


def parse_range() -> tuple[datetime, datetime]:
    end_value = request.args.get("end")
    start_value = request.args.get("start")
    end = datetime.fromisoformat(end_value) if end_value else datetime.utcnow()
    start = datetime.fromisoformat(start_value) if start_value else end - timedelta(days=7)
    if start >= end:
        raise ValueError("The start date must be before the end date.")
    return start, end


def json_number(value: Any) -> float | int | None:
    return float(value) if value is not None else None


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/api/metrics")
def metrics():
    try:
        start, end = parse_range()
        query = """
            SELECT
                AVG(avg_temperature) AS average_temperature,
                AVG(avg_humidity) AS average_humidity,
                MIN(min_temperature) AS minimum_temperature,
                MAX(max_temperature) AS maximum_temperature,
                SUM(reading_count) AS total_readings
            FROM hourly_sensor_metrics
            WHERE bucket >= %s AND bucket < %s;
        """
        with get_connection() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (start, end))
            result = cursor.fetchone()
        return jsonify({key: json_number(value) for key, value in result.items()})
    except (ValueError, psycopg2.Error) as error:
        return jsonify(error=str(error)), 400 if isinstance(error, ValueError) else 503


@app.get("/api/hourly")
def hourly():
    try:
        start, end = parse_range()
        query = """
            SELECT bucket, sensor_id, avg_temperature, avg_humidity,
                   min_temperature, max_temperature, reading_count
            FROM hourly_sensor_metrics
            WHERE bucket >= %s AND bucket < %s
            ORDER BY bucket, sensor_id;
        """
        with get_connection() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (start, end))
            rows = cursor.fetchall()
        return jsonify(rows)
    except (ValueError, psycopg2.Error) as error:
        return jsonify(error=str(error)), 400 if isinstance(error, ValueError) else 503


@app.get("/api/sensors")
def sensors():
    try:
        start, end = parse_range()
        query = """
            SELECT sensor_id, COUNT(*) AS reading_count,
                   AVG(temperature) AS average_temperature,
                   AVG(humidity) AS average_humidity,
                   MIN(temperature) AS minimum_temperature,
                   MAX(temperature) AS maximum_temperature,
                   MAX(recorded_at) AS last_reading
            FROM sensor_data
            WHERE recorded_at >= %s AND recorded_at < %s
            GROUP BY sensor_id
            ORDER BY sensor_id;
        """
        with get_connection() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (start, end))
            rows = cursor.fetchall()
        return jsonify(rows)
    except (ValueError, psycopg2.Error) as error:
        return jsonify(error=str(error)), 400 if isinstance(error, ValueError) else 503


def explain_query(connection, query: str, parameters: tuple[datetime, datetime]) -> dict[str, Any]:
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query, parameters)
        plan = cursor.fetchone()[0][0]
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "execution_time_ms": elapsed_ms,
        "planning_time_ms": plan.get("Planning Time"),
        "execution_time_reported_ms": plan.get("Execution Time"),
        "rows_returned": plan.get("Plan", {}).get("Actual Rows"),
        "plan": plan,
    }


@app.get("/api/performance")
def performance():
    """Compare actual EXPLAIN ANALYZE plans; no benchmark values are hardcoded."""
    try:
        start, end = parse_range()
        raw_query = """
            SELECT recorded_at, sensor_id, temperature, humidity
            FROM sensor_data
            WHERE recorded_at >= %s AND recorded_at < %s
            ORDER BY recorded_at;
        """
        aggregate_query = """
            SELECT bucket, sensor_id, avg_temperature, avg_humidity,
                   min_temperature, max_temperature, reading_count
            FROM hourly_sensor_metrics
            WHERE bucket >= %s AND bucket < %s
            ORDER BY bucket, sensor_id;
        """
        with get_connection() as connection:
            return jsonify({
                "range": {"start": start.isoformat(), "end": end.isoformat()},
                "raw_hypertable": explain_query(connection, raw_query, (start, end)),
                "continuous_aggregate": explain_query(connection, aggregate_query, (start, end)),
            })
    except (ValueError, psycopg2.Error) as error:
        return jsonify(error=str(error)), 400 if isinstance(error, ValueError) else 503


@app.errorhandler(errors.UndefinedTable)
def handle_missing_table(error):
    return jsonify(error="Database schema is not installed. Run schema.sql first."), 503


if __name__ == "__main__":
    app.run(host=os.getenv("FLASK_HOST", "127.0.0.1"), port=int(os.getenv("FLASK_PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
