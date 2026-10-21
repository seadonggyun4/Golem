"""Real client lifecycle fixture with an exclusively loopback, synthetic model.

Not a provider adapter: no real credentials, external model or product Work.
"""
from contextlib import contextmanager
import http.server
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import threading
import time

import codex_hosted


def npm_target():
    system = {"darwin": "darwin", "linux": "linux"}.get(sys.platform)
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}.get(platform.machine())
    if system is None or architecture is None:
        raise ValueError("unsupported native client fixture platform")
    return system + "-" + architecture


def npm_clients(prefix):
    root = Path(prefix).resolve(strict=True) / "node_modules"
    target = npm_target()
    result = {}
    for name, package, filenames in (
        ("codex-cli", root / "@openai" / ("codex-" + target), ("codex",)),
        ("claude-code", root / "@anthropic-ai" / ("claude-code-" + target), ("claude", "claude.exe"))):
        if not package.is_dir() or package.is_symlink():
            raise ValueError("missing native package: " + name)
        matches, count = [], 0
        for directory, dirs, files in os.walk(package, followlinks=False):
            count += len(dirs) + len(files)
            if count > 128 or any((Path(directory) / item).is_symlink() for item in (*dirs, *files)):
                raise ValueError("unsafe native package inventory")
            matches.extend(Path(directory) / item for item in files if item in filenames)
        if len(matches) != 1:
            raise ValueError("missing or ambiguous native client: " + name)
        result[name] = matches[0].resolve(strict=True)
    return result


@contextmanager
def provider():
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"data":[]}')

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8388608:
                self.send_error(413)
                return
            value = json.loads(self.rfile.read(size))
            requests.append((self.path, value))
            if "count_tokens" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"input_tokens":1}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            text = "D3 synthetic fixture acknowledgement."
            if "responses" in self.path:
                item = {"type": "message", "id": "msg_fixture", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}]}
                events = [
                    {"type": "response.created", "response": {"id": "resp_fixture", "status": "in_progress", "output": []}},
                    {"type": "response.output_item.added", "output_index": 0,
                     "item": {**item, "status": "in_progress", "content": []}},
                    {"type": "response.output_text.delta", "item_id": "msg_fixture", "output_index": 0,
                     "content_index": 0, "delta": text},
                    {"type": "response.output_item.done", "output_index": 0, "item": item},
                    {"type": "response.completed", "response": {"id": "resp_fixture", "status": "completed",
                     "output": [item], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}}]
            else:
                events = [
                    {"type": "message_start", "message": {"id": "msg_fixture", "type": "message", "role": "assistant",
                        "model": value.get("model", "fixture"), "content": [], "stop_reason": None,
                        "usage": {"input_tokens": 1, "output_tokens": 0}}},
                    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
                    {"type": "content_block_stop", "index": 0},
                    {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": 1}},
                    {"type": "message_stop"}]
            try:
                for event in events:
                    self.wfile.write(("event: " + event["type"] + "\ndata: " + json.dumps(event) + "\n\n").encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def environment(home):
    home.mkdir(mode=0o700, exist_ok=True)
    return {"HOME": str(home), "CODEX_HOME": str(home), "CLAUDE_CONFIG_DIR": str(home),
        "PATH": "/usr/bin:/bin", "SHELL": "/bin/sh", "LANG": "C", "LC_ALL": "C",
        "TMPDIR": str(home), "TERM": "dumb", "ANTHROPIC_API_KEY": "d3-local-fixture-not-a-secret",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1",
        "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}


@contextmanager
def codex(binary, home, cwd, config):
    (home / "config.toml").write_text(config)
    with (home / "codex-stderr.log").open("ab") as errors:
        child = subprocess.Popen([str(binary), "app-server", "--listen", "stdio://"],
            cwd=cwd, env=environment(home), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=errors, start_new_session=True)
        transport = codex_hosted.Transport(child, time.monotonic() + 120)
        try:
            transport.send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "golem_hook_fixture", "version": "1"},
                "capabilities": {"experimentalApi": True}}})
            transport.response(1)
            transport.send({"method": "initialized", "params": {}})
            yield transport
        finally:
            transport.close()
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=10)
            child.stdin.close()
            child.stdout.close()


def codex_turn(transport, request_id, thread_id):
    transport.send({"id": request_id, "method": "turn/start", "params": {"threadId": thread_id,
        "input": [{"type": "text", "text": "Synthetic local fixture: acknowledge without tools."}]}})
    while True:
        message = transport.receive()
        if message.get("id") == request_id and "error" in message:
            raise AssertionError(message["error"])
        if message.get("method") == "turn/completed":
            turn = message["params"]["turn"]
            if turn.get("error"):
                raise AssertionError(turn["error"])
            return


def contains_notice(requests, *, source=None, code=None):
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
    return any('"schema":"golem.integration-hook-notice.v1"' in text and
        (source is None or f'"source":"{source}"' in text) and
        (code is None or f'"code":"{code}"' in text)
        for _, value in requests for text in strings(value))
