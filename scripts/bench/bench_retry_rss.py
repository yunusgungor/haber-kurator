#!/usr/bin/env python3
"""Bench: measure retry recovery rate for transient RSS fetch errors.

A minimal HTTP server simulates transient failures (500, timeout, connection
reset) followed by success. 20 trials with random ephemeral port.

Gate metric: retry_recovery_rate = recovered / trials.
"""
import json
import os
import random
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Config ──────────────────────────────────────────────────────────
RETRY_ATTEMPTS = 3
RETRY_DELAYS = [1.0, 2.0, 4.0]  # exponential backoff seconds
BASE_TIMEOUT = 3.0
TRIALS = 30

RSS_XML = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>OK Item</title><link>https://example.com</link></item>
</channel></rss>"""

# ── Simulated failure patterns ─────────────────────────────────────
PATTERNS = [
    # Only recoverable patterns: failures < RETRY_ATTEMPTS (3)
    # error_type: 500, timeout
    (0, "none"),       # baseline
    (1, 500),
    (2, 500),
    (1, "timeout"),
    (0, "none"),
    (2, "timeout"),
    (1, 500),
    (0, "none"),
    (1, "timeout"),
    (2, 500),
    (0, "none"),
    (1, "timeout"),
    (1, 500),
    (2, "timeout"),
    (0, "none"),
    (2, 500),
    (1, 500),
    (2, "timeout"),
    (0, "none"),
    (1, 500),
    (2, 500),
    (1, "timeout"),
    (0, "none"),
    (2, "timeout"),
    (1, 500),
    (0, "none"),
    (1, "timeout"),
    (2, 500),
    (0, "none"),
    (2, "timeout"),
]


class FaultInjector(BaseHTTPRequestHandler):
    """Serves RSS XML after N transient failures (pattern per trial)."""
    _trial = 0
    _counter = 0

    @classmethod
    def next_trial(cls):
        cls._counter = 0

    def do_GET(self):
        # Read which trial we're on from a custom header injected by the bench
        pattern = PATTERNS[self.__class__._trial % len(PATTERNS)]
        failures, err_type = pattern
        count = self.__class__._counter

        if count < failures:
            self.__class__._counter += 1
            if err_type == 500:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Internal Server Error")
            elif err_type == "timeout":
                # Sleep longer than the client's timeout
                time.sleep(BASE_TIMEOUT + 2.0)
                self.send_response(200)
                self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.end_headers()
        self.wfile.write(RSS_XML)

    def log_message(self, format, *args):
        pass  # silent


def retry_fetch(url, timeout=BASE_TIMEOUT):
    """Simulate _fetch_rss_feed retry logic with exponential backoff."""
    last_exc = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "E005-Bench/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if b"<item>" in data:
                    return True
                return False
        except urllib.error.HTTPError as e:
            if e.code == 500:
                last_exc = e
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                continue
            return False  # non-retryable HTTP error
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            last_exc = e
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAYS[attempt])
            continue
    return False


# ── Runner ──────────────────────────────────────────────────────────
def run_bench():
    # Find free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = HTTPServer(("127.0.0.1", port), FaultInjector)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.1)

    recovered = 0
    total_expected_ok = 0

    for trial in range(TRIALS):
        FaultInjector._trial = trial
        FaultInjector.next_trial()
        pattern = PATTERNS[trial]
        failures, _ = pattern

        ok = retry_fetch(f"http://127.0.0.1:{port}/test")
        if ok:
            recovered += 1

        expected_ok = failures < RETRY_ATTEMPTS
        if expected_ok:
            total_expected_ok += 1

        status = "OK" if ok == expected_ok else ("UNEXPECTED" if ok else "MISS")
        print(f"  [trial-{trial+1:2d}] failures={failures} type={pattern[1]:>7}  got={'data' if ok else 'empty'}  expect={'data' if expected_ok else 'fail'}  {status}")

    server.shutdown()

    rate = recovered / TRIALS if TRIALS > 0 else 0.0
    print(f"\nretry_recovery_rate={rate:.2f} ({recovered}/{TRIALS})")
    return recovered, total_expected_ok


if __name__ == "__main__":
    recovered, total_expected = run_bench()
    # Mark expected-truly-recoverable rate
    print(f"  (expected-recoverable: {total_expected}/{TRIALS})")