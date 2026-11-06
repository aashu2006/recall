"""Prisma STT client (Gnani). See docs/gnani-api.md.

- REST (POST /stt/v3) for clips up to 30 s. Voice notes are split with Silero VAD into
  <= 30 s chunks; our own chunk offsets become the segment timestamps for audio proof.
- Batch (/stt/v3/batch/jobs) for long calls, when we need server-side segments or speakers.

Chunks are sent sequentially (parallel requests can hit 429). Before calling Gnani, check
calls.audio_hash (SHA-256) and reuse the cached transcript. Never call this in tests.
"""
