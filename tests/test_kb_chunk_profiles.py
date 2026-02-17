"""Chunk profile selection tests."""

from apps.backend.services.kb_ingest import _chunk_profile_for_ext


def test_chunk_profile_for_tabular_files():
    max_chars, overlap = _chunk_profile_for_ext(".csv")
    assert max_chars == 700
    assert overlap == 120


def test_chunk_profile_for_media_files():
    max_chars, overlap = _chunk_profile_for_ext(".mp4")
    assert max_chars == 1000
    assert overlap == 120


def test_chunk_profile_for_default_doc():
    max_chars, overlap = _chunk_profile_for_ext(".docx")
    assert max_chars == 1200
    assert overlap == 200

