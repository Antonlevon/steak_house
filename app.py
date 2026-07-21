"""Public-facing Site Flask app for this workspace.

Edit this file (and add modules / blueprints as needed). The site-http
systemd service auto-restarts on file changes via inotify.

Reachable from the internet only when the workspace's site mode is `open`,
or to workspace members + invitees when it's `authorized`. When mode is
`off`, nginx returns 403 to all visitors and traffic never reaches this
process.

DB access uses the local site_db (peer auth via Unix socket). The chat
agent (running as `agent`) and the Whiteboard app (running as `console`)
can also read and write site_db; this `site` process cannot reach
console_db.
"""
from __future__ import annotations

import importlib
import pkgutil

from flask import Flask, render_template

from src.db import init_db_app

app = Flask(__name__, static_folder='static')
# Must match the nginx allowlist in /etc/nginx/conf.d/site-rate-limit.conf.
app.config["SESSION_COOKIE_NAME"] = "site_session"


# <SITE_APP_DISCOVERY v1>  — must run BEFORE init_db_app so blueprint
# models land on Base.metadata in time for create_all().
try:
    import applications as _apps_pkg
    _discovered_blueprints = []
    for _mod_info in pkgutil.iter_modules(_apps_pkg.__path__):
        if _mod_info.name.startswith("_"):
            continue
        _mod = importlib.import_module(f"applications.{_mod_info.name}")
        _bp = getattr(_mod, "blueprint", None)
        if _bp is not None:
            _discovered_blueprints.append(_bp)
except ModuleNotFoundError:
    _discovered_blueprints = []
# </SITE_APP_DISCOVERY>


init_db_app(app)


# <SITE_APP_REGISTER v1>  — no url_prefix so blueprints own their full path.
for _bp in _discovered_blueprints:
    app.register_blueprint(_bp)
# </SITE_APP_REGISTER>


RESERVE_URL = "https://www.opentable.com/"

MENU = [
    {
        "image": "/static/images/ribeye.jpg",
        "name": "40-Day Dry-Aged Bone-In Ribeye",
        "desc": "Painted Hills beef, aged on the bone, seared over oak coal. Bordelaise, smoked marrow.",
        "cut": "22 oz · for two",
        "price": "$124",
    },
    {
        "image": "/static/images/filet.jpg",
        "name": "Coal-Roasted Filet",
        "desc": "Center-cut tenderloin, brushed with alderwood butter, finished at the edge of the fire.",
        "cut": "8 oz",
        "price": "$58",
    },
    {
        "image": "/static/images/porterhouse.jpg",
        "name": "The Hearth Porterhouse",
        "desc": "Strip and filet on one bone, dry-aged 35 days, salt-crust rest. Charred lemon.",
        "cut": "32 oz · for two",
        "price": "$142",
    },
    {
        "image": "/static/images/wagyu.jpg",
        "name": "Cast-Iron Wagyu Cap",
        "desc": "Snake River Farms ribeye cap, rolled and seared black-and-blue, flaked sea salt.",
        "cut": "6 oz",
        "price": "$76",
    },
    {
        "image": "/static/images/chicken.jpg",
        "name": "Ember Half-Chicken",
        "desc": "Brick-pressed over coals, preserved-lemon jus, drippings potatoes. Not everything is beef.",
        "cut": "free-range",
        "price": "$38",
    },
    {
        "image": "/static/images/chateaubriand.jpg",
        "name": "Fire-Roasted Chateaubriand",
        "desc": "Whole tenderloin roast carved tableside, red-wine shallot, bone-marrow bearnaise.",
        "cut": "for two · 20 min",
        "price": "$156",
    },
]


def _build_sparks(n: int = 26) -> list[dict]:
    """Deterministic ember field: rising sparks with varied size/drift/timing.
    Rendered once server-side (no per-visitor cost); animated purely in CSS."""
    import random

    rng = random.Random(42)  # fixed seed -> stable markup across renders
    sparks = []
    for _ in range(n):
        sparks.append(
            {
                "x": round(rng.uniform(4, 96), 1),        # horizontal start %
                "size": round(rng.uniform(2, 5), 1),       # px
                "peak": round(rng.uniform(0.5, 1.0), 2),   # max opacity
                "drift": round(rng.uniform(-40, 40), 1),   # sideways drift px
                "lift": round(rng.uniform(180, 420), 0),   # rise height px
                "dur": round(rng.uniform(4.5, 9.5), 1),    # rise duration s
                "delay": round(rng.uniform(0, 8), 1),      # start offset s
            }
        )
    return sparks


@app.route("/")
def home() -> str:
    from datetime import datetime
    return render_template(
        "index.html",
        menu=MENU,
        reserve_url=RESERVE_URL,
        year=datetime.now().year,
        sparks=_build_sparks(),
    )
