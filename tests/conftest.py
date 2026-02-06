"""Pytest fixtures."""
import os
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PASSWORD", "changeme")
os.environ.setdefault("REDIS_HOST", "localhost")
