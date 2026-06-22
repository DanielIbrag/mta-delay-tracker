# MTA Delay Collector — Setup

## 1. Install dependencies

Open Terminal and run:

```bash
pip install requests gtfs-realtime-bindings protobuf
```

## 2. Run the collector

Navigate to the folder where you saved `mta_collector.py`, then:

```bash
python mta_collector.py
```

You'll see log output like:
```
2026-06-21 14:00:00  INFO      Starting collector — polling every 60s. Press Ctrl+C to stop.
2026-06-21 14:00:01  INFO        ACE        312 stop-time updates
2026-06-21 14:00:02  INFO        BDFM       289 stop-time updates
...
2026-06-21 14:00:08  INFO      Poll complete — 2,041 rows saved
```

A file called `mta_delays.db` will be created in the same folder. **Leave it running** — the longer it runs, the more data you accumulate.

## 4. Peek at your data

To verify it's working, open a new Terminal tab and run:

```bash
sqlite3 mta_delays.db "SELECT route_id, COUNT(*) as rows FROM trip_updates GROUP BY route_id ORDER BY rows DESC LIMIT 10;"
```

## What's being collected

Every 60 seconds, the script hits all 8 MTA subway feeds and saves one row per **stop-time update** — meaning for each train, at each upcoming stop, we record:

| Column | What it means |
|---|---|
| `route_id` | Subway line (e.g. "A", "1", "L") |
| `trip_id` | Unique ID for this trip |
| `stop_id` | Station stop code |
| `arrival_delay` | Seconds late (negative = early) |
| `departure_delay` | Seconds late at departure |
| `collected_at` | When we polled the feed |

## Next steps (Stage 2)

Once you have a few days of data, open a Jupyter notebook and start asking questions:
- Which lines have the highest average delay?
- What time of day is worst?
- Which stations appear most often in delay cascades?
