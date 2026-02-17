docker logs --since 30m teachbaseai-worker-1 2>&1 | grep -E "file_id.?41|kb_ingest|ingest|ffmpeg|transcrib|ERROR|Traceback" | tail -n 120
