import os
from pathlib import Path

COLLECTOR_PORT = int(os.getenv("COLLECTOR_PORT", "9876"))
SQLITE_PATH = os.getenv("SQLITE_PATH", str(Path.home() / ".claude" / "metrics.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(Path.home() / ".claude" / "metrics-collector.log"))
