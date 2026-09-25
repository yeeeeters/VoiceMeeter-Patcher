#!/usr/bin/env python3
"""Minimal VoiceMeeter license-service protocol emulator.

This emulates the HTTP boundary used by VoiceMeeter 3.1.2.2. It does not
decrypt request envelopes or sign new certificates; those operations require
the vendor's private key material.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, urlsplit


DEFAULT_PATH = "/en/module/vblicensing/certify"


def _clean_reply(value: str) -> str:
    reply = value.strip("\r\n")
    if not (reply.startswith(">") or reply.startswith("ERROR")):
        raise ValueError("a reply must begin with '>' or 'ERROR'")
    return reply


@dataclass
class EmulatorConfig:
    path: str = DEFAULT_PATH
    mode: str = "error"
    error_reply: str = "ERROR: local license emulator has no matching response"
    grant_reply: str = ">AERO-LAB-GRANT<"
    fixed_reply: str | None = None
    replay_map: Mapping[str, str] = field(default_factory=dict)
    max_cmd_length: int = 16384

    def validate(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("path must start with '/'")
        if self.mode not in {"error", "grant", "fixed", "replay"}:
            raise ValueError("mode must be error, grant, fixed, or replay")
        if not self.error_reply.startswith("ERROR"):
            raise ValueError("error_reply must begin with 'ERROR'")
        if self.mode == "fixed" and self.fixed_reply is None:
            raise ValueError("fixed mode requires fixed_response_file")
        if self.fixed_reply is not None:
            self.fixed_reply = _clean_reply(self.fixed_reply)
        self.grant_reply = _clean_reply(self.grant_reply)
        self.replay_map = {
            key.lower(): _clean_reply(value) for key, value in self.replay_map.items()
        }


def load_config(path: Path) -> EmulatorConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = path.resolve().parent

    fixed_reply = None
    fixed_file = raw.get("fixed_response_file")
    if fixed_file:
        fixed_reply = (base / fixed_file).read_text(encoding="utf-8")

    replay_map: Mapping[str, str] = {}
    replay_file = raw.get("replay_map_file")
    if replay_file:
        replay_map = json.loads((base / replay_file).read_text(encoding="utf-8"))

    config = EmulatorConfig(
        path=raw.get("path", DEFAULT_PATH),
        mode=raw.get("mode", "error"),
        error_reply=raw.get(
            "error_reply", "ERROR: local license emulator has no matching response"
        ),
        grant_reply=raw.get("grant_reply", ">AERO-LAB-GRANT<"),
        fixed_reply=fixed_reply,
        replay_map=replay_map,
        max_cmd_length=int(raw.get("max_cmd_length", 16384)),
    )
    config.validate()
    return config


class EmulatorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config: EmulatorConfig, quiet: bool = False):
        self.config = config
        self.quiet = quiet
        self.last_fingerprint: str | None = None
        super().__init__(address, LicenseHandler)


class LicenseHandler(BaseHTTPRequestHandler):
    server: EmulatorServer
    protocol_version = "HTTP/1.1"
    server_version = "VoiceMeeterLicenseEmulator/1.0"

    def _send_text(self, status: int, reply: str) -> None:
        body = reply.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path != self.server.config.path:
            self._send_text(404, "ERROR: unknown endpoint")
            return

        values = parse_qs(parsed.query, keep_blank_values=True).get("cmd", [])
        if len(values) != 1 or not values[0]:
            self._send_text(400, "ERROR: exactly one non-empty cmd parameter is required")
            return

        cmd = values[0]
        if len(cmd) > self.server.config.max_cmd_length:
            self._send_text(413, "ERROR: cmd parameter exceeds configured limit")
            return

        fingerprint = hashlib.sha256(cmd.encode("utf-8")).hexdigest()
        self.server.last_fingerprint = fingerprint
        config = self.server.config

        if not self.server.quiet:
            print(
                f"request from {self.client_address[0]} "
                f"cmd_length={len(cmd)} cmd_sha256={fingerprint}",
                flush=True,
            )

        if config.mode == "grant":
            reply = config.grant_reply
        elif config.mode == "fixed":
            reply = config.fixed_reply or config.error_reply
        elif config.mode == "replay":
            reply = config.replay_map.get(fingerprint, config.error_reply)
        else:
            reply = config.error_reply
        self._send_text(200, reply)

    def log_message(self, _format: str, *_args) -> None:
        # BaseHTTPRequestHandler logs the full URL, which contains the opaque
        # encrypted cmd envelope. Deliberately log only its hash in do_GET().
        return


def create_server(
    host: str, port: int, config: EmulatorConfig, quiet: bool = False
) -> EmulatorServer:
    config.validate()
    return EmulatorServer((host, port), config, quiet=quiet)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.example.json"),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--cert", type=Path, help="PEM TLS certificate chain")
    parser.add_argument("--key", type=Path, help="PEM TLS private key")
    parser.add_argument("--once", action="store_true", help="handle one request and exit")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if bool(args.cert) != bool(args.key):
        print("--cert and --key must be supplied together", file=sys.stderr)
        return 2

    try:
        config = load_config(args.config)
        server = create_server(args.host, args.port, config, quiet=args.quiet)
        scheme = "http"
        if args.cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(args.cert, args.key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            scheme = "https"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(
            f"listening on {scheme}://{args.host}:{args.port}{config.path} "
            f"mode={config.mode}",
            flush=True,
        )
    try:
        if args.once:
            server.handle_request()
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
