"""Runtime configuration, read from environment variables (or a local .env file)."""
import os

try:  # python-dotenv is optional; plain environment variables always work
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


class Config:
    WAQI_API_TOKEN = os.getenv("WAQI_API_TOKEN", "")
    METEOMATICS_USERNAME = os.getenv("METEOMATICS_USERNAME", "")
    METEOMATICS_PASSWORD = os.getenv("METEOMATICS_PASSWORD", "")
    HOST = os.getenv("SKYSENTRY_HOST", "127.0.0.1")
    PORT = int(os.getenv("SKYSENTRY_PORT", "5000"))
    DEBUG = os.getenv("SKYSENTRY_DEBUG", "0") == "1"
