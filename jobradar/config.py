"""Config and base infrastructure: reading config.json, fatal exit, logs.

config.json lives under HOME (paths, ADR-0007). If profile.json exists, the
candidate's role overrides the feeds and L0 from config.json — the old
no-profile behavior is untouched, so existing runs and tests are unaffected.
"""

import json
import logging
import os
import sys

from jobradar import paths

log = logging.getLogger("jobradar")


def die(message):
    log.error(message)
    sys.stderr.write(message + "\n")
    sys.exit(1)


def load_config():
    if not os.path.exists(paths.config_path()):
        die(
            "No config.json next to the script. "
            "Copy config.example.json to config.json and fill it in."
        )
    with open(paths.config_path(), encoding="utf-8") as fh:
        cfg = json.load(fh)
    # Account/output settings (LLM, Telegram, notify threshold, heartbeat) live in
    # the profile now, so config.json has nothing required left to validate here.

    # The profile's role (if any) drives WHAT and HOW to scan: feeds and L0
    # come from the role, not from config.json.
    try:
        from jobradar import candidate

        if os.path.exists(paths.profile_json_path()):
            data = candidate.load()
            cfg.setdefault("sources", {}).setdefault("dou", {})["feeds"] = (
                candidate.effective_feeds(cfg, data)
            )
            cfg["sources"].setdefault("djinni", {})["feeds"] = (
                candidate.effective_djinni_feeds(cfg, data)
            )
            cfg["l0"] = candidate.effective_l0(cfg, data)
            log.info("Profile: role %s drives feeds and L0", data.get("role"))
    except Exception as exc:
        log.warning("Profile didn't apply to config, keeping config.json: %s", exc)
    return cfg


def setup_logging(verbose):
    handlers = [
        logging.FileHandler(paths.log_path(), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        handlers=handlers,
    )
