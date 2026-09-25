import hashlib
import threading
import unittest
import urllib.error
import urllib.request

from server import DEFAULT_PATH, EmulatorConfig, create_server


class RunningServer:
    def __init__(self, config):
        self.server = create_server("127.0.0.1", 0, config, quiet=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def get(url):
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status, response.read().decode("utf-8")


class EmulatorTests(unittest.TestCase):
    def test_grant_mode_accepts_any_nonempty_command(self):
        config = EmulatorConfig(mode="grant", grant_reply=">AERO-LAB-GRANT<")
        with RunningServer(config) as base:
            first = get(f"{base}{DEFAULT_PATH}?cmd=first-random-envelope")
            second = get(f"{base}{DEFAULT_PATH}?cmd=unrelated-envelope")
        self.assertEqual(first, (200, ">AERO-LAB-GRANT<"))
        self.assertEqual(second, (200, ">AERO-LAB-GRANT<"))

    def test_error_mode_matches_client_error_prefix(self):
        config = EmulatorConfig(mode="error", error_reply="ERROR: deliberate test")
        with RunningServer(config) as base:
            status, body = get(f"{base}{DEFAULT_PATH}?cmd=opaque-envelope")
        self.assertEqual(status, 200)
        self.assertEqual(body, "ERROR: deliberate test")

    def test_fixed_mode_returns_certificate_verbatim(self):
        certificate = ">captured-certificate-body<"
        config = EmulatorConfig(mode="fixed", fixed_reply=certificate)
        with RunningServer(config) as base:
            status, body = get(f"{base}{DEFAULT_PATH}?cmd=fresh-envelope")
        self.assertEqual(status, 200)
        self.assertEqual(body, certificate)

    def test_replay_mode_keys_on_decoded_cmd_sha256(self):
        cmd = "ABC%2B123"
        decoded_cmd = "ABC+123"
        digest = hashlib.sha256(decoded_cmd.encode()).hexdigest()
        config = EmulatorConfig(
            mode="replay", replay_map={digest: ">mapped-certificate<"}
        )
        with RunningServer(config) as base:
            status, body = get(f"{base}{DEFAULT_PATH}?cmd={cmd}")
        self.assertEqual(status, 200)
        self.assertEqual(body, ">mapped-certificate<")

    def test_missing_cmd_is_rejected(self):
        with RunningServer(EmulatorConfig()) as base:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                get(f"{base}{DEFAULT_PATH}")
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
