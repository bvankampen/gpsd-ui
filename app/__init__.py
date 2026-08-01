#!/usr/bin/env python3
"""GPSD Web UI - Real-time GPS monitoring dashboard."""

from pathlib import Path

from flask import Flask, render_template
from flask_socketio import SocketIO

from app.config import GPSD_HOST, GPSD_PORT, NTP_ENABLED, NTP_HOST, WEB_HOST, WEB_PORT

ROOT_DIR = Path(__file__).parent.parent

app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "templates"),
    static_folder=str(ROOT_DIR / "static"),
)
app.config["SECRET_KEY"] = "gpsd-ui-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Shared state
gps_data = {
    "connected": False,
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "speed": None,
    "course": None,
    "climb": None,
    "mode": 0,
    "satellites": [],
    "hdop": None,
    "vdop": None,
    "pdop": None,
    "time": None,
    "epx": None,
    "epy": None,
    "epv": None,
    "eps": None,
    "epc": None,
    "devices": [],
    "device": None,
}

ntp_data = {
    "enabled": NTP_ENABLED,
    "connected": False,
    "host": NTP_HOST,
    "time": None,
    "offset": None,
    "delay": None,
    "stratum": None,
    "ref_id": None,
    "ref_time": None,
    "leap": None,
    "precision": None,
    "root_delay": None,
    "root_dispersion": None,
}


@app.route("/")
def index():
    """Serve the main dashboard page."""
    return render_template("index.html")


@app.route("/api/gps")
def api_gps():
    """REST endpoint for current GPS data."""
    return gps_data


@socketio.on("connect")
def handle_connect():
    """Handle new WebSocket connection."""
    app.logger.info("Client connected via WebSocket")
    socketio.emit("gps_update", gps_data)
    socketio.emit("ntp_update", ntp_data)
