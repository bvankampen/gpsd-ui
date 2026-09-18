#!/usr/bin/env python3
"""GPSD Web UI - Entry point."""

import logging
import sys
import threading

from app import app, socketio, gps_data, ntp_data
from app.config import LOG_LEVEL, GPSD_HOST, GPSD_PORT, GPSD_STALL_TIMEOUT, NTP_ENABLED, NTP_HOST, UPDATE_INTERVAL, WEB_HOST, WEB_PORT
from app.gpsd_reader import gpsd_reader
from app.ntp_reader import ntp_reader

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
numeric_level = LOG_LEVELS.get(LOG_LEVEL, logging.INFO)


class AccessLogFilter(logging.Filter):
    """Filter to suppress GET/POST access logs unless DEBUG."""
    def filter(self, record):
        if numeric_level > logging.DEBUG:
            msg = record.getMessage()
            if "GET " in msg or "POST " in msg:
                return False
        return True


# Set up logging
logging.root.setLevel(numeric_level)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(numeric_level)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
if numeric_level > logging.DEBUG:
    handler.addFilter(AccessLogFilter())
logging.root.addHandler(handler)

app.logger.setLevel(numeric_level)
app.logger.propagate = False
app.logger.addHandler(handler)


def main():
    """Entry point."""
    app.logger.info("=" * 60)
    app.logger.info("GPSD Web UI - Real-time GPS Satellite Dashboard")
    app.logger.info("=" * 60)
    app.logger.info("Configuration:")
    app.logger.info(f"  Log level    : {LOG_LEVEL}")
    app.logger.info(f"  GPSD host    : {GPSD_HOST}:{GPSD_PORT}")
    app.logger.info(f"  GPSD stall   : {GPSD_STALL_TIMEOUT}s without data")
    app.logger.info(f"  Update interval: {UPDATE_INTERVAL}s")
    app.logger.info(f"  NTP enabled  : {NTP_ENABLED}")
    if NTP_ENABLED:
        app.logger.info(f"  NTP host     : {NTP_HOST}")
    app.logger.info(f"  Web bind     : {WEB_HOST}:{WEB_PORT}")
    app.logger.info("=" * 60)

    # Start gpsd reader thread
    app.logger.info("Starting GPSD reader thread...")
    reader = threading.Thread(
        target=gpsd_reader,
        args=(app, socketio, gps_data, GPSD_HOST, GPSD_PORT, UPDATE_INTERVAL, GPSD_STALL_TIMEOUT),
        daemon=True,
    )
    reader.start()

    # Start NTP reader thread if enabled
    if NTP_ENABLED:
        app.logger.info("Starting NTP reader thread...")
        ntp_thread = threading.Thread(
            target=ntp_reader,
            args=(app, socketio, ntp_data, NTP_HOST, UPDATE_INTERVAL),
            daemon=True,
        )
        ntp_thread.start()
    else:
        app.logger.info("NTP disabled - skipping NTP reader thread")

    app.logger.info("Starting web server...")
    socketio.run(app, host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    main()
