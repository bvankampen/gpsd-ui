#!/usr/bin/env python3
"""GPSD Web UI - GPSD reader thread."""

import json
import socket
import time


def parse_gpsd_response(line):
    """Parse a JSON response from gpsd."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def update_gps_data(data, gps_data):
    """Update shared GPS data from gpsd response."""
    if data.get("class") == "DEVICES":
        gps_data["devices"] = [d["path"] for d in data.get("devices", [])]

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
        if "satellites" in data:
            gps_data["satellites"] = [
                {
                    "PRN": s.get("PRN"),
                    "az": s.get("az"),
                    "el": s.get("el"),
                    "ss": s.get("ss"),
                    "used": s.get("used", False),
                    "gnssid": s.get("gnssid", 0),
                    "svid": s.get("svid"),
                }
                for s in data["satellites"]
            ]
        if "hdop" in data:
            gps_data["hdop"] = data["hdop"]
        if "vdop" in data:
            gps_data["vdop"] = data["vdop"]
        if "pdop" in data:
            gps_data["pdop"] = data["pdop"]


def gpsd_reader(app, socketio, gps_data, gpsd_host, gpsd_port, update_interval):
    """Background thread that reads data from gpsd."""
    while True:
        try:
            app.logger.info(f"Connecting to gpsd at {gpsd_host}:{gpsd_port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((gpsd_host, gpsd_port))
            sock.settimeout(2.0)

            # Read the version banner
            banner = sock.recv(4096).decode("utf-8", errors="replace")
            banner_data = parse_gpsd_response(banner)
            if banner_data:
                app.logger.info(f"gpsd banner: {banner_data}")

            # Enable watching
            sock.sendall(b'?WATCH={"enable":true,"json":true}\n')

            gps_data["connected"] = True
            socketio.emit("gps_status", {"connected": True})
            app.logger.info("Connected - watching gpsd data stream")

            buffer = ""
            last_emit = 0

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
                                sats_used = len([s for s in gps_data.get("satellites", []) if s.get("used")])
                                app.logger.debug(
                                    f"TPV: mode={mode} lat={lat} lon={lon} sats_used={sats_used}"
                                )
                            elif msg_class == "SKY":
                                sats = data.get("satellites", [])
                                hdop = data.get("hdop")
                                app.logger.debug(
                                    f"SKY: satellites={len(sats)} hdop={hdop}"
                                )
                            elif msg_class == "DEVICES":
                                devices = [d.get("path") for d in data.get("devices", [])]
                                app.logger.info(f"Devices detected: {devices}")
                            elif msg_class == "DEVICE":
                                app.logger.info(f"Active device: {data.get('path')}")

                            update_gps_data(data, gps_data)

                            now = time.time()
                            if now - last_emit >= update_interval:
                                socketio.emit("gps_update", gps_data)
                                last_emit = now

                except socket.timeout:
                    continue

        except (ConnectionRefusedError, OSError) as e:
            app.logger.error(f"gpsd connection failed: {e}")
            gps_data["connected"] = False
            socketio.emit("gps_status", {"connected": False})

        finally:
            try:
                sock.close()
            except Exception:
                pass

        app.logger.info("Reconnecting in 5s...")
        time.sleep(5)
