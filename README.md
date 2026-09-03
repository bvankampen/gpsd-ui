# GPSD Web UI

![Screenshot](docs/screenshot.png)

Real-time GPS satellite monitoring dashboard with polar sky plot and NTP time display.

## Features

- Polar sky plot showing satellite positions by azimuth/elevation
- GNSS constellation color coding (GPS, Galileo, GLONASS, BeiDou, SBAS)
- Satellite table with PRN, type, coordinates, signal strength, and usage status
- Satellite table filtering by constellation/PRN and used-in-fix status
- GPS time display with live incrementing seconds
- Receiver position, speed, course, and climb telemetry
- NTP time synchronization with offset, delay, stratum, and precision
- WebSocket real-time updates with separate browser and GPS connection status
- REST snapshots at `/api/gps` and `/api/ntp`, plus `/health` for monitoring
- Containerized deployment with Docker

## Quick Start

### Local

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
python3 run.py
```

### Docker

```bash
docker build -t gpsd-ui .
docker run -p 5000:5000 --env-file .env gpsd-ui
```

## Configuration

Configuration via `config.yaml` or environment variables (env vars override config.yaml):

| Env Var | Default | Description |
|---------|---------|-------------|
| `GPSD_HOST` | localhost | GPS daemon host |
| `GPSD_PORT` | 2947 | GPS daemon port |
| `NTP_ENABLED` | false | Enable NTP display |
| `NTP_HOST` | pool.ntp.org | NTP server |
| `UPDATE_INTERVAL` | 1 | Update interval in seconds (GPS and NTP) |
| `WEB_HOST` | 0.0.0.0 | Flask bind address |
| `WEB_PORT` | 5000 | Flask port |
| `CORS_ALLOWED_ORIGINS` | same-origin | Comma-separated origins allowed to use Socket.IO |
| `LOG_LEVEL` | INFO | Logging level |

When GPSD is unavailable, `/health` returns HTTP 503 with a `degraded` status; it returns HTTP 200 once GPSD is connected.

## Monitoring API

| Endpoint | Description |
|----------|-------------|
| `GET /api/gps` | Current GPS position, fix, accuracy, device, and satellite data |
| `GET /api/ntp` | Current NTP synchronization data |
| `GET /health` | Service health; HTTP 503 indicates GPSD is disconnected |

## Tests

Run the backend contract and parser tests with:

```bash
python3 -m unittest discover -s tests -v
```

The test suite does not require a running GPSD instance.

## Architecture

```text
gpsd-ui/
├── app/
│   ├── __init__.py        # Flask app, routes, socketio events
│   ├── config.py          # YAML/env config loader
│   ├── gpsd_reader.py     # GPSD socket reader thread
│   └── ntp_reader.py      # NTP query thread
├── static/
│   ├── style.css          # CSS styles
│   └── app.js             # JavaScript (WebSocket, polar plot, tables)
├── templates/
│   └── index.html         # HTML template
├── tests/
│   └── test_app.py        # API and GPSD parsing tests
├── config.example.yaml    # Example config
├── Dockerfile
└── requirements.txt
```

## Tech Stack

- **Backend**: Python, Flask, Flask-SocketIO, gevent
- **Frontend**: Vanilla JavaScript, Socket.IO, HTML5 Canvas
- **Data sources**: gpsd (socket), NTP (ntplib)

## License

[MIT License](LICENSE) - Author: Bas van Kampen <bas@ping6.nl>

