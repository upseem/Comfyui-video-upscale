"""Pure, dependency-free chunk planning. Context is trimmed, not blended."""
from __future__ import annotations


def chunk_plan(frame_count: int, chunk_index: int, chunk_size: int, context: int) -> dict[str, int]:
    if frame_count < 1 or chunk_size < 1 or context < 0:
        raise ValueError("Invalid frame_count, chunk_size or context")
    count = (frame_count + chunk_size - 1) // chunk_size
    if not 0 <= chunk_index < count:
        raise ValueError("Chunk index out of range")
    start = chunk_index * chunk_size
    end = min(start + chunk_size, frame_count)
    read_start = max(0, start - context)
    read_end = min(frame_count, end + context)
    return dict(frame_count=frame_count, chunk_index=chunk_index,
                chunk_size=chunk_size, context=context,
                start=start, end=end, read_start=read_start, read_end=read_end,
                trim_left=start-read_start, keep_count=end-start,
                read_count=read_end-read_start)


def validate_plan(plan: dict, frame_count: int, image_count: int) -> None:
    expected = chunk_plan(frame_count, plan['chunk_index'], plan['chunk_size'], plan['context'])
    if plan != expected:
        raise ValueError("Stale or malformed chunk plan")
    if image_count != plan['read_count']:
        raise ValueError(f"Upscaler changed frame count: expected {plan['read_count']}, got {image_count}")
