#!/usr/bin/env python3
"""GPSD Web UI - Configuration loader."""

import os
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# Load config.yaml if it exists
config = {}
if CONFIG_PATH.exists():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f) or {}

GPSD_CFG = config.get("gpsd", {})
NTP_CFG = config.get("ntp", {})
WEB_CFG = config.get("web", {})


def env(key, default=None):
    """Get value from environment variable, falling back to default."""
    val = os.environ.get(key)
    if val is None:
        return default
    return val


def env_bool(key, default=False):
    """Get boolean from environment variable."""
    val = env(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")


def env_int(key, default=None):
    """Get integer from environment variable."""
    val = env(key)
    if val is None:
        return default
    return int(val)


def env_list(key, default=None):
    """Get a comma-separated or YAML list value from the environment/config."""
    val = env(key, default)
    if not val:
        return None
    if isinstance(val, str):
        return [item.strip() for item in val.split(",") if item.strip()]
    return val

LOG_LEVEL = env("LOG_LEVEL", config.get("log_level", "INFO")).upper()
GPSD_HOST = env("GPSD_HOST", GPSD_CFG.get("host", "localhost"))
GPSD_PORT = env_int("GPSD_PORT", GPSD_CFG.get("port", 2947))
GPSD_STALL_TIMEOUT = env_int(
    "GPSD_STALL_TIMEOUT", GPSD_CFG.get("stall_timeout", 30)
)
NTP_ENABLED = env_bool("NTP_ENABLED", NTP_CFG.get("enabled", False))
NTP_HOST = env("NTP_HOST", NTP_CFG.get("host", "pool.ntp.org"))
UPDATE_INTERVAL = env_int("UPDATE_INTERVAL", config.get("update_interval", 1))
WEB_HOST = env("WEB_HOST", WEB_CFG.get("host", "0.0.0.0"))
WEB_PORT = env_int("WEB_PORT", WEB_CFG.get("port", 5000))
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", WEB_CFG.get("cors_allowed_origins")
)
