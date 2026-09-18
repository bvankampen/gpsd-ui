#!/usr/bin/env python3
"""GPSD Web UI - GPSD reader thread."""

import json
import socket
import time

# Kernel keepalive probes for the long-lived gpsd connection. A peer that
# disappears without a FIN/RST leaves the socket half-open, where recv() never
# returns and never errors; the probes force the failure to surface.
KEEPALIVE_IDLE = 30
KEEPALIVE_INTERVAL = 10
KEEPALIVE_PROBES = 3


def configure_keepalive(sock, app):
    """Enable TCP keepalive with a short idle window on the gpsd socket."""
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, KEEPALIVE_IDLE)
        if hasattr(socket, "TCP_KEEPINTVL"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, KEEPALIVE_INTERVAL)
        if hasattr(socket, "TCP_KEEPCNT"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, KEEPALIVE_PROBES)
    except OSError as e:
        app.logger.warning(f"Could not tune gpsd socket keepalive: {e}")


def parse_gpsd_response(line):
    """Parse a JSON object response from gpsd."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None

def update_gps_data(data, gps_data):
    """Update shared GPS data from gpsd response."""
    if data.get("class") == "DEVICES":
        gps_data["devices"] = [
            device.get("path")
            for device in data.get("devices", [])
            if isinstance(device, dict) and device.get("path")
        ]

    elif data.get("class") == "DEVICE":
        gps_data["device"] = data.get("path")

    elif data.get("class") == "TPV":
        if "lat" in data:
            gps_data["latitude"] = data["lat"]
        if "lon" in data:
            gps_data["longitude"] = data["lon"]
        if "alt" in data:
            gps_data["altitude"] = data["alt"]
        if "speed" in data:
            gps_data["speed"] = data["speed"]
        if "track" in data:
            gps_data["course"] = data["track"]
        if "climb" in data:
            gps_data["climb"] = data["climb"]
        if "mode" in data:
            gps_data["mode"] = data["mode"]
        if "time" in data:
            gps_data["time"] = data["time"]
        if "epx" in data:
            gps_data["epx"] = data["epx"]
        if "epy" in data:
            gps_data["epy"] = data["epy"]
        if "epv" in data:
            gps_data["epv"] = data["epv"]
        if "eps" in data:
            gps_data["eps"] = data["eps"]
        if "epc" in data:
            gps_data["epc"] = data["epc"]

    elif data.get("class") == "SKY":
        satellites = data.get("satellites")
        if isinstance(satellites, list):
            gps_data["satellites"] = [
                {
                    "PRN": satellite.get("PRN"),
                    "az": satellite.get("az"),
                    "el": satellite.get("el"),
                    "ss": satellite.get("ss"),
                    "used": satellite.get("used", False),
                    "gnssid": satellite.get("gnssid", 0),
                    "svid": satellite.get("svid"),
                }
                for satellite in satellites
                if isinstance(satellite, dict)
            ]
        if "hdop" in data:
            gps_data["hdop"] = data["hdop"]
        if "vdop" in data:
            gps_data["vdop"] = data["vdop"]
        if "pdop" in data:
            gps_data["pdop"] = data["pdop"]


def gpsd_reader(
    app, socketio, gps_data, gpsd_host, gpsd_port, update_interval, stall_timeout=30
):
    """Background thread that reads data from gpsd.

    ``gps_data["connected"]`` reports the data stream, not the TCP session: it
    is set once messages arrive and cleared when the connection ends or when no
    message has arrived for ``stall_timeout`` seconds. A silent peer must never
    be presented as a live feed.
    """
    while True:
        sock = None
        try:
            app.logger.info(f"Connecting to gpsd at {gpsd_host}:{gpsd_port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((gpsd_host, gpsd_port))
            sock.settimeout(2.0)
            configure_keepalive(sock, app)

            # Read the version banner
            banner = sock.recv(4096).decode("utf-8", errors="replace")
            banner_data = parse_gpsd_response(banner)
            if banner_data:
                app.logger.info(f"gpsd banner: {banner_data}")

            # Enable watching
            sock.sendall(b'?WATCH={"enable":true,"json":true}\n')

            app.logger.info("Connected - waiting for gpsd data")

            buffer = ""
            last_emit = 0
            last_message = time.time()

            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        app.logger.warning("gpsd connection closed by remote")
                        break
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        data = parse_gpsd_response(line)
                        if data:
                            msg_class = data.get("class", "unknown")
                            if msg_class == "TPV":
                                mode = data.get("mode", 0)
                                lat = data.get("lat")
                                lon = data.get("lon")
                                sats_used = len(
                                    [s for s in gps_data.get("satellites", []) if s.get("used")]
                                )
                                app.logger.debug(
                                    f"TPV: mode={mode} lat={lat} lon={lon} sats_used={sats_used}"
                                )
                            elif msg_class == "SKY":
                                sats = data.get("satellites") or []
                                hdop = data.get("hdop")
                                app.logger.debug(
                                    f"SKY: satellites={len(sats)} hdop={hdop}"
                                )
                            elif msg_class == "DEVICES":
                                devices = [
                                    d.get("path")
                                    for d in data.get("devices", [])
                                    if isinstance(d, dict) and d.get("path")
                                ]
                                app.logger.info(f"Devices detected: {devices}")
                            elif msg_class == "DEVICE":
                                app.logger.info(f"Active device: {data.get('path')}")

                            update_gps_data(data, gps_data)

                            now = time.time()
                            last_message = now
                            gps_data["last_update"] = now
                            if not gps_data["connected"]:
                                gps_data["connected"] = True
                                socketio.emit("gps_status", {"connected": True})
                            if now - last_emit >= update_interval:
                                socketio.emit("gps_update", gps_data)
                                last_emit = now
                except socket.timeout:
                    silence = time.time() - last_message
                    if silence >= stall_timeout:
                        app.logger.warning(
                            f"No gpsd data for {silence:.0f}s - reconnecting"
                        )
                        break
                    continue

        except (ConnectionRefusedError, OSError) as e:
            app.logger.error(f"gpsd connection failed: {e}")
        finally:
            try:
                if sock is not None:
                    sock.close()
            except OSError:
                pass
            if gps_data["connected"]:
                gps_data["connected"] = False
                socketio.emit("gps_status", {"connected": False})

        app.logger.info("Reconnecting in 5s...")
        time.sleep(5)
