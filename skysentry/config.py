"""Runtime configuration. SkySentry needs no API keys; everything is optional."""
import os

try:  # python-dotenv is optional; plain environment variables always work
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


class Config:
    HOST = os.getenv("SKYSENTRY_HOST", "127.0.0.1")
    PORT = int(os.getenv("SKYSENTRY_PORT", "5000"))
    DEBUG = os.getenv("SKYSENTRY_DEBUG", "0") == "1"
    CACHE_SECONDS = int(os.getenv("SKYSENTRY_CACHE_SECONDS", "600"))
