#!/usr/bin/env python3
"""GPSD Web UI - NTP reader thread."""

import time

import ntplib


def ntp_reader(app, socketio, ntp_data, ntp_host, ntp_interval):
    """Background thread that queries NTP server."""
    client = ntplib.NTPClient()
    app.logger.info(f"NTP reader started - querying {ntp_host} every {ntp_interval}s")

    while True:
        try:
            response = client.request(ntp_host, version=3)
            ntp_data["connected"] = True
            ntp_data["time"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(response.tx_time)
            )
            ntp_data["offset"] = response.offset
            ntp_data["delay"] = response.delay
            ntp_data["stratum"] = response.stratum
            ntp_data["ref_id"] = response.ref_id
            ntp_data["ref_time"] = time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(response.ref_time)
            )
            ntp_data["leap"] = response.leap
            ntp_data["precision"] = response.precision
            ntp_data["root_delay"] = response.root_delay
            ntp_data["root_dispersion"] = response.root_dispersion
            app.logger.debug(
                f"NTP response: offset={response.offset*1000:.2f}ms "
                f"delay={response.delay*1000:.2f}ms stratum={response.stratum}"
            )
            socketio.emit("ntp_update", ntp_data)
        except Exception as e:
            app.logger.warning(f"NTP query failed: {e}")
            ntp_data["connected"] = False
            socketio.emit("ntp_update", ntp_data)

        time.sleep(ntp_interval)
