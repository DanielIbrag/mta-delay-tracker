"""
MTA Delay Data Collector
========================
Polls MTA GTFS-Realtime feeds every 60 seconds and stores trip update
(delay) data in a local SQLite database.

No API key required — MTA subway feeds are free and open.

Setup:
    pip install requests gtfs-realtime-bindings protobuf

Usage:
    python mta_collector.py
"""

import time
import sqlite3
import logging
import requests
from datetime import datetime
from typing import Optional
from google.transit import gtfs_realtime_pb2

# Each URL covers a group of subway lines.
# Full list: https://api.mta.info/#/subwayRealTimeFeeds
FEEDS = {
    "ACE":    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "BDFM":   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "G":      "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
    "JZ":     "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "NQRW":   "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "L":      "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
    "123456S":"https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "7":      "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-7",
}

DB_PATH    = "mta_delays.db"
POLL_SECS  = 60   # how often to poll each feed

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db(path: str) -> sqlite3.Connection:
    """Create tables if they don't exist and return a connection."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trip_updates (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at      TEXT    NOT NULL,   -- ISO timestamp when we polled
            feed_group        TEXT    NOT NULL,   -- e.g. "ACE"
            trip_id           TEXT,
            route_id          TEXT,
            start_date        TEXT,
            start_time        TEXT,
            direction_id      INTEGER,
            stop_id           TEXT,
            arrival_delay     INTEGER,            -- seconds; negative = early
            departure_delay   INTEGER,
            arrival_time      INTEGER,            -- scheduled Unix time
            departure_time    INTEGER
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_collected_at ON trip_updates(collected_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_route_id ON trip_updates(route_id)
    """)
    conn.commit()
    log.info("Database ready at %s", path)
    return conn


def insert_rows(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany("""
        INSERT INTO trip_updates (
            collected_at, feed_group, trip_id, route_id,
            start_date, start_time, direction_id,
            stop_id, arrival_delay, departure_delay,
            arrival_time, departure_time
        ) VALUES (
            :collected_at, :feed_group, :trip_id, :route_id,
            :start_date, :start_time, :direction_id,
            :stop_id, :arrival_delay, :departure_delay,
            :arrival_time, :departure_time
        )
    """, rows)
    conn.commit()

# ---------------------------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------------------------

def fetch_feed(url: str) -> Optional[gtfs_realtime_pb2.FeedMessage]:
    """Download and parse a GTFS-RT protobuf feed."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        msg = gtfs_realtime_pb2.FeedMessage()
        msg.ParseFromString(resp.content)
        return msg
    except Exception as exc:
        log.warning("Failed to fetch %s — %s", url, exc)
        return None


def parse_trip_updates(feed: gtfs_realtime_pb2.FeedMessage,
                       feed_group: str,
                       collected_at: str) -> list[dict]:
    """Extract one row per stop-time-update from a feed message."""
    rows = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu   = entity.trip_update
        trip = tu.trip
        for stu in tu.stop_time_update:
            rows.append({
                "collected_at":    collected_at,
                "feed_group":      feed_group,
                "trip_id":         trip.trip_id or None,
                "route_id":        trip.route_id or None,
                "start_date":      trip.start_date or None,
                "start_time":      trip.start_time or None,
                "direction_id":    trip.direction_id if trip.HasField("direction_id") else None,
                "stop_id":         stu.stop_id or None,
                "arrival_delay":   stu.arrival.delay   if stu.HasField("arrival")   else None,
                "departure_delay": stu.departure.delay if stu.HasField("departure") else None,
                "arrival_time":    stu.arrival.time    if stu.HasField("arrival")   else None,
                "departure_time":  stu.departure.time  if stu.HasField("departure") else None,
            })
    return rows

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def poll_once(conn: sqlite3.Connection) -> None:
    collected_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    total = 0
    for group, url in FEEDS.items():
        feed = fetch_feed(url)
        if feed is None:
            continue
        rows = parse_trip_updates(feed, group, collected_at)
        if rows:
            insert_rows(conn, rows)
            total += len(rows)
            log.info("  %-10s  %d stop-time updates", group, len(rows))
    log.info("Poll complete — %d rows saved", total)


def main() -> None:
    conn = init_db(DB_PATH)

    log.info("Starting collector — polling every %ds. Press Ctrl+C to stop.", POLL_SECS)
    try:
        while True:
            poll_once(conn)
            time.sleep(POLL_SECS)
    except KeyboardInterrupt:
        log.info("Stopped.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
