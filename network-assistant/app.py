#!/usr/bin/env python3
"""
Network Topology Assistant — a Cisco Network Assistant-style tool.

Logs into switches via SSH, discovers neighbors using CDP/LLDP,
and presents an interactive topology map in the browser.
"""

import json
import logging
import os
import threading

import yaml
from flask import Flask, jsonify, render_template, request

from discovery import TopologyDiscovery

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

# Global state
_config = {}
_discovery = None
_discovery_lock = threading.Lock()
_discovery_running = False
_log_messages = []


def load_config(path=None):
    if path is None:
        path = os.environ.get(
            "NET_ASSISTANT_CONFIG",
            os.path.join(os.path.dirname(__file__), "config.yaml"),
        )
    if not os.path.exists(path):
        logger.warning(f"Config file not found at {path}, using empty config")
        return {"seed_devices": [], "defaults": {}, "discovery": {}, "web": {}}
    with open(path) as f:
        return yaml.safe_load(f)


def _progress_callback(message, topology):
    _log_messages.append(message)
    # Keep last 200 messages
    if len(_log_messages) > 200:
        _log_messages.pop(0)


# ── Routes ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    """Return current config (credentials redacted)."""
    safe = json.loads(json.dumps(_config))
    if "defaults" in safe:
        for key in ("password", "secret"):
            if key in safe["defaults"]:
                safe["defaults"][key] = "***"
    for seed in safe.get("seed_devices", []):
        for key in ("password", "secret"):
            if key in seed:
                seed[key] = "***"
    return jsonify(safe)


@app.route("/api/config/seeds", methods=["POST"])
def update_seeds():
    """Update seed devices. Body: { seeds: [{host, username?, password?, ...}] }"""
    global _config, _discovery
    data = request.get_json()
    if not data or "seeds" not in data:
        return jsonify({"error": "Missing 'seeds' array"}), 400
    _config["seed_devices"] = data["seeds"]
    # Also update defaults if provided
    if "defaults" in data:
        _config["defaults"] = data["defaults"]
    _discovery = TopologyDiscovery(_config)
    _discovery.on_progress(_progress_callback)
    return jsonify({"status": "ok", "seed_count": len(data["seeds"])})


@app.route("/api/discover", methods=["POST"])
def start_discovery():
    """Start topology discovery in a background thread."""
    global _discovery_running, _discovery
    with _discovery_lock:
        if _discovery_running:
            return jsonify({"error": "Discovery already running"}), 409

        if not _config.get("seed_devices"):
            return jsonify({"error": "No seed devices configured"}), 400

        _discovery = TopologyDiscovery(_config)
        _discovery.on_progress(_progress_callback)
        _log_messages.clear()
        _discovery_running = True

    def run():
        global _discovery_running
        try:
            _discovery.discover()
        finally:
            with _discovery_lock:
                _discovery_running = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/topology", methods=["GET"])
def get_topology():
    """Return current topology data."""
    if _discovery is None:
        return jsonify({"devices": {}, "links": []})
    topo = _discovery.get_topology()
    topo["running"] = _discovery_running
    return jsonify(topo)


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Return discovery log messages."""
    since = request.args.get("since", 0, type=int)
    return jsonify({"messages": _log_messages[since:], "total": len(_log_messages)})


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _config = load_config()
    _discovery = TopologyDiscovery(_config)
    _discovery.on_progress(_progress_callback)

    web = _config.get("web", {})
    host = web.get("host", "0.0.0.0")
    port = web.get("port", 5000)

    logger.info(f"Starting Network Assistant on {host}:{port}")
    app.run(host=host, port=port, debug=True, use_reloader=False)
