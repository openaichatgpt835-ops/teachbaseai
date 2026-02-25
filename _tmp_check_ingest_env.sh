docker exec teachbaseai-worker-ingest-4 env | grep -E 'ENABLE_SPEAKER_DIARIZATION|PYANNOTE_TOKEN' | sed 's/hf_.*/hf_***MASKED***/'
