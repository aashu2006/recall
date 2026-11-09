# Eval

Synthetic Hinglish voice notes run through the real backend code, scored per PRD "Evaluation".
Synthetic data only: the clients are the ones in `backend/scripts/seed.py`.

| File | What |
| --- | --- |
| `cases.json` | 10 voice note scripts + expected items. New order, quantity, rate and date changes, two items in one note, an ambiguous update (Gupta has two open MS sheet orders), a noisy note (3 dB SNR) |
| `make_audio.py` | Voices each script with Timbre (Poorvi / Vikrant alternating, `hi-en`), then makes a noisy 8 kHz phone copy with ffmpeg |
| `run_eval.py` | `stt.transcribe` -> `extract.extract` -> `matcher.match` per case, on clean and noisy audio. Writes `results.md` |
| `out/` | Gitignored: audio, transcript cache, `results.json` with every transcript and decision |

## Run

From the repo root (the scripts import `backend/app`, so they run in the backend's uv env):

```bash
uv run --project backend python eval/make_audio.py --dry-run             # what would be voiced
uv run --project backend python eval/make_audio.py                       # 10 Timbre calls, asks first
uv run --project backend --with jiwer python eval/run_eval.py --dry-run  # what would be transcribed
uv run --project backend --with jiwer python eval/run_eval.py            # 20 Prisma calls, asks first
```

Try one case before the full set: `--only C06` on both scripts (`--variants clean` on run_eval).

## Credits

- `make_audio.py` skips audio that already exists. Delete a file to voice it again.
- `run_eval.py` caches every transcript in `out/transcripts/` keyed by audio SHA-256 + STT
  settings + keyterms. Re-runs (new prompts, new matcher) cost no Prisma credits. Changing the
  STT model/format or a seed order (keyterms) transcribes again, on purpose.
- Both scripts ask before spending credits (`--yes` to skip the question).
- LLM calls (Groq / Gemini) run every time. `--no-match` skips the matcher calls.

## Metrics

- **WER / CER**: corpus level against each case's `reference` (Prisma codemix style: Hindi in
  Devanagari, English in Latin). Punctuation, case, nukta and chandrabindu are normalised.
- **Extraction accuracy**: expected items whose item, quantity, rate and delivery date are all
  right. Values the client didn't say must come back null (an update that restates the old rate
  is wrong). Spec, unit and kind are reported per field.
- **Matching accuracy**: new orders created, updates linked to the right order id, the
  ambiguous update sent to the owner with both candidates.
- **Confirmation rate**: extracted items the pipeline would send to `pending_confirmations`.
- **Latency**: Prisma (as measured when first transcribed), extract + match, and their sum.
  No DB or WhatsApp time.

Dates are resolved against the fixed `call_time` in `cases.json` (Mon 9 Nov 2026, 10:30 IST).

## Tests

```bash
uv run --project backend --with jiwer pytest eval/tests   # all APIs mocked, real HTTP blocked
```
