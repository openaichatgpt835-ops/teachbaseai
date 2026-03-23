from __future__ import annotations

from typing import Any


def merge_transcript_items(
    items: list[dict[str, Any]],
    *,
    max_gap_ms: int = 3000,
    max_duration_ms: int = 120000,
    max_chars: int = 1800,
) -> list[dict[str, Any]]:
    """Merge consecutive transcript items for the same speaker.

    Keeps chronological order and merges only adjacent rows with same speaker,
    close timestamps, and reasonable final block size.
    """
    if not items:
        return []

    out: list[dict[str, Any]] = []
    for it in items:
        row = dict(it)
        speaker = str(row.get("speaker") or "").strip() or "Спикер A"
        text = str(row.get("text") or "").strip()
        start_ms = int(row.get("start_ms") or 0)
        end_ms = int(row.get("end_ms") or start_ms)
        row["speaker"] = speaker
        row["text"] = text
        row["start_ms"] = start_ms
        row["end_ms"] = end_ms

        if not out:
            out.append(row)
            continue

        prev = out[-1]
        prev_speaker = str(prev.get("speaker") or "").strip() or "Спикер A"
        if prev_speaker != speaker:
            out.append(row)
            continue

        prev_start = int(prev.get("start_ms") or 0)
        prev_end = int(prev.get("end_ms") or prev_start)
        gap = max(0, start_ms - prev_end)
        merged_duration = max(prev_end, end_ms) - min(prev_start, start_ms)
        merged_chars = len(str(prev.get("text") or "")) + 1 + len(text)
        if gap > max_gap_ms or merged_duration > max_duration_ms or merged_chars > max_chars:
            out.append(row)
            continue

        prev_text = str(prev.get("text") or "").strip()
        if prev_text and text:
            prev["text"] = f"{prev_text} {text}"
        elif text:
            prev["text"] = text
        prev["end_ms"] = max(prev_end, end_ms)

    return out


