"""Tests the tool-calling loop against a fake Ollama server (no real model needed)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from wuwa_tracker.core import probability as pr
from wuwa_tracker.core.analysis import all_stats
from wuwa_tracker.core.ollama_client import OllamaClient, ToolBox
from tests.test_core import mk


class FakeOllama(BaseHTTPRequestHandler):
    calls = []
    tools_supported = True

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"models": [{"name": "qwen2.5:7b"}, {"name": "gemma:2b"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.calls.append(req)
        if "tools" in req and not FakeOllama.tools_supported:
            return self._send(400, {"error": "registry.ollama.ai/library/gemma:2b does not support tools"})
        last = req["messages"][-1]
        if "tools" in req and last["role"] == "user":
            return self._send(200, {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "featured_probability", "arguments": {"pool_type": 1, "pulls": 80}}}]}})
        content = last["content"] if last["role"] == "tool" else "no-tools answer"
        self._send(200, {"message": {"role": "assistant", "content": "ANSWER " + content}})


def _server():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _toolbox():
    stats = all_stats(mk(1, [("x", 3)] * 30))
    return ToolBox(lambda: stats, pr.hazard_community)


def test_tool_loop():
    srv = _server()
    FakeOllama.tools_supported = True
    c = OllamaClient(f"http://127.0.0.1:{srv.server_port}")
    assert c.list_models() == ["gemma:2b", "qwen2.5:7b"]
    seen = []
    ans, msgs = c.chat("qwen2.5:7b", [{"role": "user", "content": "odds?"}], _toolbox(),
                       on_tool=lambda n, a, r: seen.append((n, r)))
    assert seen[0][0] == "featured_probability"
    expected = round(pr.featured_distribution(pr.hazard_community(), 80, 1, 30).probability * 100, 2)
    assert seen[0][1]["probability_percent"] == expected and seen[0][1]["start_pity"] == 30
    assert ans.startswith("ANSWER") and str(expected) in ans
    srv.shutdown()


def test_fallback_without_tools():
    srv = _server()
    FakeOllama.tools_supported = False
    c = OllamaClient(f"http://127.0.0.1:{srv.server_port}")
    ans, _ = c.chat("gemma:2b", [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}], _toolbox())
    assert ans == "ANSWER no-tools answer"
    assert "pre-computed facts" in FakeOllama.calls[-1]["messages"][0]["content"]
    srv.shutdown()


def test_toolbox_errors_are_returned():
    tb = _toolbox()
    assert "error" in tb.run("featured_probability", {"pulls": 10})       # missing pool_type
    assert tb.run("pulls_needed", {"pool_type": 1, "copies": 1})["pulls_for_90pct"] > 0
