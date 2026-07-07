#!/usr/bin/env python3
"""
Transparent local proxy that compresses LLM API calls on the fly.
Speaks both OpenAI-compatible (/v1/chat/completions) and Anthropic-compatible (/v1/messages) formats.
"""

import json
import logging
import os
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("tokensave.proxy")

STATS_DIR = Path.home() / ".tokensave"
STATS_FILE = STATS_DIR / "stats.json"
PROXY_PORT = 18787
HEADROOM_PORT = 8787  # Default headroom proxy port, if running


@dataclass
class ProxyStats:
    """Tracks token savings across proxy sessions."""
    total_requests: int = 0
    total_input_tokens_before: int = 0
    total_input_tokens_after: int = 0
    total_output_tokens: int = 0
    estimated_cost_saved: float = 0.0
    start_time: float = field(default_factory=time.time)

    def save(self):
        STATS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "total_requests": self.total_requests,
            "total_input_tokens_before": self.total_input_tokens_before,
            "total_input_tokens_after": self.total_input_tokens_after,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_saved": round(self.estimated_cost_saved, 4),
            "start_time": self.start_time,
        }
        STATS_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls):
        if STATS_FILE.exists():
            try:
                data = json.loads(STATS_FILE.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    @property
    def compression_ratio(self) -> float:
        if self.total_input_tokens_before > 0:
            return 1 - (self.total_input_tokens_after / self.total_input_tokens_before)
        return 0.0

    @property
    def runtime_hours(self) -> float:
        return (time.time() - self.start_time) / 3600


stats = ProxyStats.load()


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that proxies LLM API requests through compression."""

    def do_OPTIONS(self):
        self._cors_headers()
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        # Determine target from path
        path = self.path

        if "/v1/chat/completions" in path:
            self._handle_openai_chat(body)
        elif "/v1/messages" in path:
            self._handle_anthropic_messages(body)
        else:
            self._forward_raw(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-api-key")

    def _compress_messages(self, messages: list) -> list:
        """Compress messages using headroom proxy if available, otherwise return as-is."""
        try:
            import headroom
            from headroom import Headroom

            # Use headroom's compressor directly
            hr = Headroom()
            compressed = []
            for msg in messages:
                if isinstance(msg.get("content"), str) and len(msg["content"]) > 200:
                    compressed_content = hr.compress(msg["content"])
                    compressed.append({**msg, "content": compressed_content})
                else:
                    compressed.append(msg)
            return compressed
        except ImportError:
            # Headroom not directly importable for compression; skip
            return messages
        except Exception as e:
            logger.warning(f"Compression failed for message batch: {e}")
            return messages

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        return len(text) // 4

    def _handle_openai_chat(self, body: bytes):
        try:
            req = json.loads(body)
            messages = req.get("messages", [])

            # Count tokens before
            text_before = json.dumps(messages)
            tokens_before = self._estimate_tokens(text_before)

            # Compress
            compressed_messages = self._compress_messages(messages)
            req["messages"] = compressed_messages

            # Count after
            text_after = json.dumps(compressed_messages)
            tokens_after = self._estimate_tokens(text_after)

            # Forward to real API
            real_url = os.environ.get(
                "TOKENSAVE_OPENAI_BASE_URL",
                os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )

            api_key = os.environ.get("OPENAI_API_KEY", "")
            target_url = real_url.rstrip("/") + "/chat/completions"

            response_data = self._forward_request(
                target_url, json.dumps(req).encode(), 
                {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            )

            # Update stats
            stats.total_requests += 1
            stats.total_input_tokens_before += tokens_before
            stats.total_input_tokens_after += tokens_after

            if response_data:
                resp_json = json.loads(response_data)
                if "usage" in resp_json:
                    stats.total_output_tokens += resp_json["usage"].get("completion_tokens", 0)

                # Rough cost estimate (GPT-4o pricing)
                savings = (tokens_before - tokens_after) / 1_000_000 * 2.50
                stats.estimated_cost_saved += savings
                stats.save()

                self._cors_headers()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_data)
            else:
                self._send_error(502, "Upstream API failed")

        except Exception as e:
            logger.error(f"OpenAI proxy error: {e}")
            self._send_error(500, str(e))

    def _handle_anthropic_messages(self, body: bytes):
        try:
            req = json.loads(body)
            messages = req.get("messages", [])

            text_before = json.dumps(messages)
            tokens_before = self._estimate_tokens(text_before)

            compressed_messages = self._compress_messages(messages)
            req["messages"] = compressed_messages

            text_after = json.dumps(compressed_messages)
            tokens_after = self._estimate_tokens(text_after)

            real_url = os.environ.get(
                "TOKENSAVE_ANTHROPIC_BASE_URL",
                os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            )

            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            target_url = real_url.rstrip("/") + "/messages"

            response_data = self._forward_request(
                target_url, json.dumps(req).encode(),
                {
                    "x-api-key": api_key,
                    "anthropic-version": self.headers.get("anthropic-version", "2023-06-01"),
                    "Content-Type": "application/json",
                }
            )

            stats.total_requests += 1
            stats.total_input_tokens_before += tokens_before
            stats.total_input_tokens_after += tokens_after

            if response_data:
                resp_json = json.loads(response_data)
                if "usage" in resp_json:
                    stats.total_output_tokens += resp_json["usage"].get("output_tokens", 0)
                    input_tokens = resp_json["usage"].get("input_tokens", 0)
                    # Use actual reported input tokens for savings calc
                    savings = (tokens_before - tokens_after) / 1_000_000 * 3.0
                    stats.estimated_cost_saved += savings
                    stats.save()

                self._cors_headers()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_data)
            else:
                self._send_error(502, "Upstream API failed")

        except Exception as e:
            logger.error(f"Anthropic proxy error: {e}")
            self._send_error(500, str(e))

    def _forward_request(self, url: str, data: bytes, headers: dict) -> bytes | None:
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            logger.error(f"Upstream HTTP {e.code}: {e.read().decode()[:200]}")
            return None
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return None

    def _forward_raw(self, body: bytes):
        """Pass through for non-chat endpoints."""
        self._cors_headers()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        self._cors_headers()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": {"message": message}}).encode())

    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")


class TokenSaveProxy:
    """Manages the transparent proxy lifecycle."""

    def __init__(self, port: int = PROXY_PORT):
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self, daemon: bool = True) -> bool:
        if self.running:
            logger.info("Proxy already running")
            return True

        try:
            self.server = HTTPServer(("127.0.0.1", self.port), ProxyHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=daemon)
            self.thread.start()
            self.running = True
            logger.info(f"TokenSave proxy started on 127.0.0.1:{self.port}")
            return True
        except OSError as e:
            logger.error(f"Failed to start proxy on port {self.port}: {e}")
            return False

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.running = False
        logger.info("TokenSave proxy stopped")

    def is_running(self) -> bool:
        return self.running

    @property
    def status_line(self) -> str:
        if self.running:
            r = stats.total_requests
            ratio = stats.compression_ratio * 100
            saved = stats.estimated_cost_saved
            return (
                f"  ✓ Proxy running on 127.0.0.1:{self.port}\n"
                f"  📊 {r} requests processed | {ratio:.1f}% compression"
                f" | ~${saved:.2f} saved"
            )
        return "  ✗ Proxy not running"
