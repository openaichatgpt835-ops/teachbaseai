docker exec teachbaseai-worker-ingest-4 python -c 'import importlib.util;print("pyannote", bool(importlib.util.find_spec("pyannote.audio")));print("torch", bool(importlib.util.find_spec("torch")))'
