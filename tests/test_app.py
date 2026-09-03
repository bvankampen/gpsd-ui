import unittest

from app import app, gps_data, socketio
from app.gpsd_reader import parse_gpsd_response, update_gps_data


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


if __name__ == "__main__":
    unittest.main()
