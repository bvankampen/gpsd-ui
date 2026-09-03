#!/usr/bin/env python3
"""GPSD Web UI - Real-time GPS monitoring dashboard."""

from pathlib import Path

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit

from app.config import (
    CORS_ALLOWED_ORIGINS,
    GPSD_HOST,
    GPSD_PORT,
    NTP_ENABLED,
    NTP_HOST,
    WEB_HOST,
    WEB_PORT,
)

ROOT_DIR = Path(__file__).parent.parent

app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "templates"),
    static_folder=str(ROOT_DIR / "static"),
)
app.config["SECRET_KEY"] = "gpsd-ui-secret"
socketio = SocketIO(app, cors_allowed_origins=CORS_ALLOWED_ORIGINS, async_mode="gevent")

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
    "last_update": None,
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

@app.route("/api/ntp")
def api_ntp():
    """REST endpoint for current NTP data."""
    return ntp_data


@app.route("/health")
def health():
    """Return service health for container/orchestrator checks."""
    healthy = gps_data["connected"]
    payload = {
        "status": "ok" if healthy else "degraded",
        "gps_connected": gps_data["connected"],
        "ntp_enabled": ntp_data["enabled"],
    }
    return jsonify(payload), 200 if healthy else 503


@socketio.on("connect")
def handle_connect():
    """Send the current state to the newly connected WebSocket client."""
    app.logger.info("Client connected via WebSocket")
    emit("gps_update", gps_data)
    emit("ntp_update", ntp_data)
