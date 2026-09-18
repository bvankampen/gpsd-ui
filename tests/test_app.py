import json
import logging
import socket
import threading
import time
import unittest

from app import app, gps_data, socketio
from app.gpsd_reader import gpsd_reader, parse_gpsd_response, update_gps_data


class ApiTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_gps_snapshot_contains_connection_state(self):
        response = self.client.get("/api/gps")

        self.assertEqual(response.status_code, 200)
        self.assertIn("connected", response.json)

    def test_ntp_snapshot_is_available(self):
        response = self.client.get("/api/ntp")

        self.assertEqual(response.status_code, 200)
        self.assertIn("enabled", response.json)

    def test_websocket_snapshot_is_not_broadcast_to_existing_clients(self):
        first = socketio.test_client(app)
        first.get_received()

        second = socketio.test_client(app)
        second_events = second.get_received()
        first_events = first.get_received()

        self.assertEqual(
            {event["name"] for event in second_events},
            {"gps_update", "ntp_update"},
        )
        self.assertEqual(first_events, [])
        first.disconnect()
        second.disconnect()

    def test_health_reports_degraded_without_gpsd(self):
        original = gps_data["connected"]
        try:
            gps_data["connected"] = False
            response = self.client.get("/health")
        finally:
            gps_data["connected"] = original

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["status"], "degraded")

    def test_health_reports_ok_with_gpsd(self):
        original = gps_data["connected"]
        try:
            gps_data["connected"] = True
            response = self.client.get("/health")
        finally:
            gps_data["connected"] = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")


class GpsdParsingTests(unittest.TestCase):
    def test_parser_accepts_only_json_objects(self):
        self.assertEqual(parse_gpsd_response('{"class":"TPV"}'), {"class": "TPV"})
        self.assertIsNone(parse_gpsd_response("not json"))
        self.assertIsNone(parse_gpsd_response("[1, 2, 3]"))

    def test_device_update_ignores_malformed_entries(self):
        state = {"devices": []}

        update_gps_data(
            {"class": "DEVICES", "devices": [{"path": "/dev/ttyUSB0"}, {}, "bad"]},
            state,
        )

        self.assertEqual(state["devices"], ["/dev/ttyUSB0"])

    def test_satellite_update_ignores_malformed_entries(self):
        state = {"satellites": []}

        update_gps_data(
            {"class": "SKY", "satellites": [{"PRN": 1}, "bad"]},
            state,
        )
        update_gps_data({"class": "SKY", "satellites": None}, state)

        self.assertEqual(len(state["satellites"]), 1)


class RecordingSocketIO:
    """Stands in for the SocketIO server; the reader only emits through it."""

    def __init__(self):
        self.events = []

    def emit(self, name, payload=None, **kwargs):
        self.events.append((name, payload))


class FakeGpsd:
    """Single-connection gpsd stand-in that can go silent without closing."""

    def __init__(self, ticks=None, period=0.1):
        self.ticks = ticks  # None streams forever, N sends N payloads then goes quiet
        self.period = period
        self.connections = 0
        self._stop = threading.Event()
        self._listener = socket.socket()
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._listener.close()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            self.connections += 1
            try:
                conn.sendall(b'{"class":"VERSION","release":"fake"}\n')
                conn.recv(4096)  # ?WATCH
                self._stream(conn)
            except OSError:
                pass
            finally:
                conn.close()

    def _stream(self, conn):
        sent = 0
        while not self._stop.is_set():
            if self.ticks is not None and sent >= self.ticks:
                self._stop.wait(30)  # stay connected, send nothing
                return
            payload = {
                "class": "TPV",
                "mode": 3,
                "lat": 51.0,
                "lon": 4.0,
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            conn.sendall((json.dumps(payload) + "\n").encode())
            sent += 1
            time.sleep(self.period)


class GpsdReaderTests(unittest.TestCase):
    def setUp(self):
        self.log_level = app.logger.level
        app.logger.setLevel(logging.CRITICAL)
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.stop()
        app.logger.setLevel(self.log_level)

    def start_reader(self, port, state, stall_timeout):
        recorder = RecordingSocketIO()
        threading.Thread(
            target=gpsd_reader,
            args=(app, recorder, state, "127.0.0.1", port, 0.1, stall_timeout),
            daemon=True,
        ).start()
        return recorder

    @staticmethod
    def wait_for(predicate, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return predicate()

    def test_silent_stream_is_reported_as_disconnected(self):
        server = FakeGpsd(ticks=1, period=0.1).start()
        self.servers.append(server)
        state = {"connected": False, "satellites": [], "last_update": None}
        recorder = self.start_reader(server.port, state, stall_timeout=1)

        self.assertTrue(self.wait_for(lambda: state["connected"], 5))
        # The fake keeps the connection open, so only the stall watchdog can
        # notice that the feed stopped.
        self.assertTrue(
            self.wait_for(lambda: state["connected"] is False, 10),
            "reader kept reporting a connected feed after gpsd went silent",
        )
        self.assertIn(("gps_status", {"connected": False}), recorder.events)
        self.assertEqual(server.connections, 1)

    def test_flowing_stream_stays_connected(self):
        server = FakeGpsd(ticks=None, period=0.2).start()
        self.servers.append(server)
        state = {"connected": False, "satellites": [], "last_update": None}
        recorder = self.start_reader(server.port, state, stall_timeout=1)

        deadline = time.time() + 3
        self.assertTrue(self.wait_for(lambda: state["connected"], 5))
        while time.time() < deadline:
            self.assertTrue(state["connected"], "live feed was reported as stale")
            time.sleep(0.2)
        self.assertEqual(server.connections, 1)

        self.assertEqual(
            [event for event in recorder.events if event[0] == "gps_status"],
            [("gps_status", {"connected": True})],
        )


if __name__ == "__main__":
    unittest.main()
