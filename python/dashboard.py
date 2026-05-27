import dataclasses
import json
import logging
import threading
from typing import Optional

import config

log = logging.getLogger(__name__)

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="2">
  <title>SeismoGuard-R</title>
  <style>
    body {{ font-family: monospace; background: #111; color: #eee; padding: 2em; }}
    .class0 {{ color: #0f0; }}
    .class1 {{ color: #ff0; }}
    .class2 {{ color: #f80; }}
    .class3 {{ color: #f00; font-weight: bold; }}
    table {{ border-collapse: collapse; }}
    td, th {{ padding: 4px 12px; border: 1px solid #444; }}
  </style>
</head>
<body>
  <h1>SeismoGuard-R Dashboard</h1>
  <p>Alert class: <span class="class{cls}">{cls}</span></p>
  <pre>{state_json}</pre>
</body>
</html>
"""


def _default(obj):
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")


def _serialise(state: dict) -> str:
    try:
        return json.dumps(state, default=_default, indent=2)
    except Exception:
        return "{}"


class DashboardServer:
    def __init__(self, shared_state: dict, state_lock: threading.Lock):
        self._state      = shared_state
        self._lock       = state_lock
        self._flask_app  = self._build_app()

    def _build_app(self):
        try:
            from flask import Flask, jsonify, Response
        except ImportError:
            log.warning("Flask not installed — dashboard disabled")
            return None

        app = Flask(__name__)
        state  = self._state
        lock   = self._lock

        @app.route("/")
        def index():
            with lock:
                snap = dict(state)
            cls      = snap.get("fsm_class", 0)
            body     = _HTML_TEMPLATE.format(cls=cls, state_json=_serialise(snap))
            return Response(body, mimetype="text/html")

        @app.route("/api/state")
        def api_state():
            with lock:
                snap = dict(state)
            return Response(_serialise(snap), mimetype="application/json")

        @app.route("/api/alert")
        def api_alert():
            with lock:
                assessment = state.get("assessment")
                fsm_class  = state.get("fsm_class", 0)
            payload = {
                "class":   fsm_class,
                "kind":    assessment.alert_kind if assessment else "all_clear",
                "Mpd":     assessment.Mpd if assessment else None,
                "flags":   assessment.flags if assessment else {},
            }
            return Response(json.dumps(payload), mimetype="application/json")

        return app

    def start(self) -> Optional[threading.Thread]:
        if self._flask_app is None:
            return None
        t = threading.Thread(
            target=self._flask_app.run,
            kwargs={"host": "0.0.0.0", "port": config.FLASK_PORT, "use_reloader": False},
            daemon=True,
            name="dashboard",
        )
        t.start()
        log.info("Dashboard running on http://0.0.0.0:%d", config.FLASK_PORT)
        return t
