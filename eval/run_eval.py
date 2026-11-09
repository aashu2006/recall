"""Run the eval set through the real backend: stt.transcribe -> extract.extract -> matcher.match.

    uv run --project backend --with jiwer python eval/run_eval.py --dry-run   # plan, no API calls
    uv run --project backend --with jiwer python eval/run_eval.py             # asks before Prisma
    uv run --project backend --with jiwer python eval/run_eval.py --only C08 --variants clean --yes

Needs eval/out/audio from make_audio.py. Writes eval/results.md (summary tables) and
eval/out/results.json (transcripts, extracted items, decisions, per item scores).

Credits: transcripts are cached in eval/out/transcripts by audio SHA-256 plus the STT
settings and keyterms, so re-runs never pay Prisma again for the same audio. The LLM
(Groq / Gemini via backend/app/llm.py) runs every time; --no-match skips the matcher calls.

Metrics, per variant (clean = Timbre audio, noisy = 8 kHz phone copy with noise):
- WER / CER: corpus level vs the case reference, after normalising punctuation and
  Devanagari nukta / chandrabindu spellings
- Extraction accuracy: expected items with item, quantity, rate and delivery date all right
- Matching accuracy: new orders created, updates linked to the right order, the ambiguous
  update sent to the owner
- Confirmation rate: extracted items the pipeline would send to pending_confirmations
- Latency: STT (measured when the transcript was first made), extract, match, end to end
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
import traceback
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from common import (CASES, EVAL_DIR, OUT, TRANSCRIPT_CACHE, clean_path, load_cases,
                    noisy_path)

import jiwer  # noqa: E402  (uv run --with jiwer)
from app import extract, matcher, stt  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.extract import IST  # noqa: E402
from scripts.seed import CLIENTS as SEED_CLIENTS  # noqa: E402

VARIANTS = ("clean", "noisy")
RESULTS_MD = EVAL_DIR / "results.md"
RESULTS_JSON = OUT / "results.json"
SCORED_FIELDS = ("item", "quantity", "rate", "delivery_date")  # "all correct" = these four
REPORT_FIELDS = ("kind", "item", "spec", "quantity", "unit", "rate", "delivery_date")


# ---------------------------------------------------------------- world: clients + orders

def build_world(call_date: date) -> dict[str, dict]:
    """Seed clients and open orders as a fresh DB would have them: ids in seed order."""
    world, order_id = {}, 0
    for client_id, c in enumerate(SEED_CLIENTS, start=1):
        client = {"id": client_id, "name": c["name"], "phone": c["phone"], "aliases": c["aliases"]}
        orders = []
        for o in c["orders"]:
            order_id += 1
            orders.append(_order(order_id, client_id, o, call_date))
        world[c["key"]] = {"client": client, "open_orders": orders}
    return world


def case_orders(case: dict, world: dict, call_date: date) -> list[dict]:
    w = world[case["client"]]
    extra = [_order(o["id"], w["client"]["id"], o, call_date) for o in case.get("extra_open_orders", [])]
    return w["open_orders"] + extra


def _order(order_id: int, client_id: int, o: dict, call_date: date) -> dict:
    return {
        "id": order_id, "client_id": client_id, "item": o["item"], "spec": o.get("spec"),
        "quantity": o.get("quantity"), "unit": o.get("unit"), "rate": o.get("rate"),
        "delivery_date": (call_date + timedelta(days=o["days"])).isoformat(), "status": "open",
    }


def expected_items(case: dict, call_date: date) -> list[dict]:
    out = []
    for e in case["expected"]:
        e = dict(e)
        days = e.pop("delivery_in_days", None)
        e["delivery_date"] = (call_date + timedelta(days=days)).isoformat() if days is not None else None
        out.append(e)
    return out


# ---------------------------------------------------------------- STT with a local cache

def stt_cache_key(audio: Path, keyterms: list[str], settings) -> str:
    audio_hash = hashlib.sha256(audio.read_bytes()).hexdigest()
    config = json.dumps([settings.gnani_stt_model, settings.gnani_stt_language_code,
                         settings.gnani_stt_format, settings.gnani_stt_max_chunk_s, keyterms],
                        ensure_ascii=False)
    return f"{audio_hash}.{hashlib.sha256(config.encode()).hexdigest()[:10]}"


def transcribe_cached(audio: Path, keyterms: list[str], settings, cache_dir: Path) -> dict:
    path = cache_dir / f"{stt_cache_key(audio, keyterms, settings)}.json"
    if path.exists():
        return {**json.loads(path.read_text()), "cached": True}
    t0 = time.perf_counter()
    result = stt.transcribe(audio, keyterms=keyterms, settings=settings)
    result["latency_s"] = round(time.perf_counter() - t0, 3)
    result["audio"] = audio.name
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return {**result, "cached": False}


# ---------------------------------------------------------------- scoring

_PUNCT = re.compile(r"[।॥,.?!;:\"'()\[\]\-–—…]")


def normalize_text(text: str) -> str:
    """Lowercase, drop punctuation, merge spellings Prisma uses interchangeably."""
    text = text.casefold().replace("़", "").replace("ँ", "ं")  # nukta, chandrabindu
    return " ".join(_PUNCT.sub(" ", text).split())


_UNITS = {"pc": "pcs", "pcs": "pcs", "piece": "pcs", "pieces": "pcs", "nos": "pcs", "no": "pcs",
          "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "किलो": "kg",
          "ton": "ton", "tons": "ton", "tonne": "ton", "m": "meter", "meter": "meter",
          "meters": "meter", "metre": "meter", "mtr": "meter"}


def _words(s: str | None) -> set[str]:
    out = set()
    for w in re.findall(r"[^\W_]+", (s or "").casefold()):
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


def item_matches(expected: str | None, got: str | None) -> bool:
    """Same item if one name's words contain the other's ("angle" ~ "MS angle")."""
    a, b = _words(expected), _words(got)
    if not a or not b:
        return not a and not b
    return a <= b or b <= a


def _spec(s) -> str:
    """"50 x 50 x 6" / "50 by 50 by 6" / "50×50×6" -> "50x50x6"."""
    s = (str(s) if s is not None else "").casefold().replace("×", "x").replace("*", "x")
    return re.sub(r"\s+", "", re.sub(r"\bby\b", "x", s))


def field_ok(field: str, expected, got) -> bool:
    if field == "item":
        return item_matches(expected, got)
    if field in ("quantity", "rate"):
        if expected is None or got is None:
            return expected is None and got is None
        return abs(float(expected) - float(got)) < 1e-6
    if field == "unit":
        if expected is None:
            return True  # not checked when the note didn't need one
        return _UNITS.get(str(got or "").casefold(), got) == _UNITS.get(expected.casefold(), expected)
    if field == "spec":
        return expected is None or _spec(expected) in _spec(got)  # "3mm" ~ "3mm MS"
    if field == "delivery_date":
        got = got.isoformat() if isinstance(got, date) else got
        return expected == got
    return expected == got


def pair_items(expected: list[dict], got: list[dict]) -> list[int | None]:
    """For each expected item, the index of the extracted item it pairs with (or None)."""
    used: set[int] = set()
    pairs: list[int | None] = []
    for e in expected:
        best, best_score = None, 0
        for i, g in enumerate(got):
            if i in used or not item_matches(e["item"], g.get("item") or g.get("order_ref")):
                continue
            score = 2 + (g.get("kind") == e["kind"])
            if score > best_score:
                best, best_score = i, score
        if best is not None:
            used.add(best)
        pairs.append(best)
    return pairs


def decision_ok(e: dict, d: dict | None) -> bool:
    if d is None:
        return False
    if e.get("expect_confirmation"):
        return d["action"] == "confirm" and set(e.get("candidates", [])) <= set(d["candidate_ids"])
    if e["kind"] == "new_order":
        return d["action"] == "create"
    return d["action"] == "update" and d["order_id"] == e["order_id"]


def score_case(expected: list[dict], items: list[dict], decisions: list[dict] | None) -> dict:
    pairs = pair_items(expected, items)
    scored = []
    for e, idx in zip(expected, pairs):
        g = items[idx] if idx is not None else None
        fields = {f: (g is not None and field_ok(f, e.get(f), g.get(f))) for f in REPORT_FIELDS}
        scored.append({
            "expected": e, "got_index": idx, "fields": fields,
            "correct": g is not None and all(fields[f] for f in SCORED_FIELDS),
            "match_ok": decision_ok(e, decisions[idx]) if decisions is not None and idx is not None else None,
        })
    paired = {i for i in pairs if i is not None}
    return {"items": scored, "extra_items": [i for i in range(len(items)) if i not in paired]}


# ---------------------------------------------------------------- running

def run_variant(case: dict, variant: str, audio: Path, ctx: dict) -> dict:
    w = ctx["world"][case["client"]]
    open_orders = case_orders(case, ctx["world"], ctx["call_date"])
    rec = {"case": case["id"], "category": case["category"], "variant": variant, "audio": audio.name}
    try:
        keyterms = stt.client_keyterms(w["client"], open_orders, ctx["settings"])
        tr = transcribe_cached(audio, keyterms, ctx["settings"], ctx["cache_dir"])
        rec.update(transcript=tr["transcript"], stt_cached=tr["cached"], stt_s=tr.get("latency_s"))
        ref, hyp = normalize_text(case["reference"]), normalize_text(tr["transcript"])
        rec.update(ref_norm=ref, hyp_norm=hyp, wer=jiwer.wer(ref, hyp) if hyp else 1.0,
                   cer=jiwer.cer(ref, hyp) if hyp else 1.0)

        t0 = time.perf_counter()
        items = extract.extract(tr["transcript"], call_time=ctx["call_time"],
                                client_name=w["client"]["name"], open_orders=open_orders)
        rec["extract_s"] = round(time.perf_counter() - t0, 3)
        rec["items"] = [i.model_dump(mode="json") for i in items]

        decisions = None
        if ctx["match"]:
            t0 = time.perf_counter()
            decisions = [asdict(matcher.match(i, open_orders)) for i in items]
            rec["match_s"] = round(time.perf_counter() - t0, 3)
            rec["decisions"] = decisions
        rec["score"] = score_case(expected_items(case, ctx["call_date"]), rec["items"], decisions)
    except Exception as e:  # one bad case must not lose the rest of a paid run
        rec["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    return rec


def aggregate(records: list[dict], cases: list[dict], variant: str, call_date: date) -> dict:
    recs = [r for r in records if r["variant"] == variant]
    by_case = {c["id"]: c for c in cases}
    ok = [r for r in recs if "error" not in r]
    n_expected = sum(len(by_case[r["case"]]["expected"]) for r in recs)
    scored = [s for r in ok for s in r["score"]["items"]]
    decisions = [d for r in ok for d in r.get("decisions") or []]
    match_scored = [s for s in scored if s["match_ok"] is not None]
    stt_s = [r["stt_s"] for r in ok if r.get("stt_s") is not None]
    llm_s = [r["extract_s"] + r.get("match_s", 0) for r in ok]
    total_s = [r["stt_s"] + r["extract_s"] + r.get("match_s", 0) for r in ok if r.get("stt_s") is not None]
    with_text = [r for r in ok if r["hyp_norm"]]
    return {
        "variant": variant, "cases": len(recs), "errors": len(recs) - len(ok),
        "wer": jiwer.wer([r["ref_norm"] for r in with_text], [r["hyp_norm"] for r in with_text]) if with_text else None,
        "cer": jiwer.cer([r["ref_norm"] for r in with_text], [r["hyp_norm"] for r in with_text]) if with_text else None,
        "expected_items": n_expected,
        "correct_items": sum(s["correct"] for s in scored),
        "extra_items": sum(len(r["score"]["extra_items"]) for r in ok),
        "field_acc": {f: sum(s["fields"][f] for s in scored) / n_expected if n_expected else None for f in REPORT_FIELDS},
        "match_total": n_expected if any("decisions" in r for r in ok) else 0,
        "match_ok": sum(bool(s["match_ok"]) for s in match_scored),
        "decisions": len(decisions),
        "confirmations": sum(d["action"] == "confirm" for d in decisions),
        "stt_s": _stats(stt_s), "llm_s": _stats(llm_s), "total_s": _stats(total_s),
    }


def _stats(xs: list[float]) -> dict | None:
    return {"median": statistics.median(xs), "max": max(xs)} if xs else None


# ---------------------------------------------------------------- report

def render_markdown(meta: dict, summaries: list[dict], records: list[dict], cases: list[dict]) -> str:
    cols = [s["variant"] for s in summaries]

    def row(label, fn):
        return f"| {label} | " + " | ".join(fn(s) for s in summaries) + " |"

    pct = lambda a, b: f"{a}/{b} ({a / b:.0%})" if b else "n/a"  # noqa: E731
    rate = lambda x: f"{x:.1%}" if x is not None else "n/a"  # noqa: E731
    secs = lambda st: f"{st['median']:.1f} s / {st['max']:.1f} s" if st else "n/a"  # noqa: E731

    lines = [
        "# Recall eval results", "",
        f"Run {meta['run_at']} · {meta['cases']} synthetic voice notes · call time {meta['call_time']} · "
        f"STT `{meta['stt_model']}` ({meta['stt_format']}) · LLM `{meta['llm']}`", "",
        "| Metric | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
        row("WER", lambda s: rate(s["wer"])),
        row("CER", lambda s: rate(s["cer"])),
        row("Extraction accuracy (item, qty, rate, date all correct)", lambda s: pct(s["correct_items"], s["expected_items"])),
        row("Extra items (not in the note)", lambda s: str(s["extra_items"])),
        row("Matching accuracy", lambda s: pct(s["match_ok"], s["match_total"]) if s["match_total"] else "skipped"),
        row("Confirmation rate (items sent to owner)", lambda s: pct(s["confirmations"], s["decisions"]) if s["decisions"] else "n/a"),
        row("STT latency, median / max", lambda s: secs(s["stt_s"])),
        row("Extract + match latency, median / max", lambda s: secs(s["llm_s"])),
        row("End to end (no DB), median / max", lambda s: secs(s["total_s"])),
    ]
    if any(s["errors"] for s in summaries):
        lines.append(row("Cases that errored", lambda s: str(s["errors"])))

    lines += ["", "Per field accuracy over expected items:", "",
              "| Field | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for f in REPORT_FIELDS:
        lines.append(row(f, lambda s, f=f: rate(s["field_acc"][f])))

    lines += ["", "Per case (items correct / expected, then the pipeline decisions):", "",
              "| Case | Category | " + " | ".join(f"WER {c} | Items {c} | Decisions {c}" for c in cols) + " |",
              "|---|---|" + "---|---|---|" * len(cols)]
    by_key = {(r["case"], r["variant"]): r for r in records}
    for c in cases:
        cells = []
        for v in cols:
            r = by_key.get((c["id"], v))
            if r is None:
                cells += ["", "", ""]
            elif "error" in r:
                cells += ["error", "", r["error"][:60].replace("|", "/")]
            else:
                good = sum(s["correct"] for s in r["score"]["items"])
                decs = ", ".join(_decision_label(d) for d in r.get("decisions") or []) or "-"
                cells += [rate(r["wer"]), f"{good}/{len(c['expected'])}", decs]
        lines.append(f"| {c['id']} | {c['category']} | " + " | ".join(cells) + " |")

    lines += ["", "Raw transcripts, extracted items and decisions: `eval/out/results.json`. "
              "Cases and expected items: `eval/cases.json`.", ""]
    return "\n".join(lines)


def _decision_label(d: dict) -> str:
    if d["action"] == "update":
        return f"update #{d['order_id']}"
    if d["action"] == "confirm":
        return "confirm" + (f" ({'/'.join(f'#{c}' for c in d['candidate_ids'])})" if d["candidate_ids"] else "")
    return d["action"]


# ---------------------------------------------------------------- main

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cases", type=Path, default=CASES)
    p.add_argument("--audio-dir", type=Path, default=OUT / "audio")
    p.add_argument("--cache-dir", type=Path, default=TRANSCRIPT_CACHE)
    p.add_argument("--only", help="comma separated case ids")
    p.add_argument("--variants", default="clean,noisy", help="clean, noisy or both")
    p.add_argument("--no-match", action="store_true", help="skip matcher LLM calls")
    p.add_argument("--out", type=Path, default=RESULTS_MD)
    p.add_argument("--json-out", type=Path, default=RESULTS_JSON)
    p.add_argument("--dry-run", action="store_true", help="print the plan, call nothing")
    p.add_argument("--yes", action="store_true", help="don't ask before calling Prisma")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = load_cases(args.cases, args.only.split(",") if args.only else None)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    if bad := set(variants) - set(VARIANTS):
        raise SystemExit(f"Unknown variants: {', '.join(bad)}")

    settings = get_settings()
    call_time = datetime.fromisoformat(data["call_time"]).astimezone(IST)
    call_date = call_time.date()
    world = build_world(call_date)
    ctx = {"world": world, "call_time": call_time, "call_date": call_date, "settings": settings,
           "cache_dir": args.cache_dir, "match": not args.no_match}

    paths = {"clean": clean_path, "noisy": noisy_path}
    jobs, missing, uncached = [], [], []
    for case in data["cases"]:
        for v in variants:
            audio = paths[v](case, args.audio_dir)
            if not audio.exists():
                missing.append(audio.name)
                continue
            jobs.append((case, v, audio))
            keyterms = stt.client_keyterms(world[case["client"]]["client"], case_orders(case, world, call_date), settings)
            if not (args.cache_dir / f"{stt_cache_key(audio, keyterms, settings)}.json").exists():
                uncached.append(audio.name)

    print(f"{len(jobs)} runs ({len(data['cases'])} cases x {', '.join(variants)}). "
          f"Prisma calls needed: {len(uncached)} files, the rest are cached. "
          f"LLM calls: ~{len(jobs)} extract{'' if args.no_match else ' + 1 match per item'}.")
    if missing:
        print(f"Missing audio (run make_audio.py first): {', '.join(missing)}")
    for name in uncached:
        print(f"  STT {name}")
    if args.dry_run or not jobs:
        return 0 if args.dry_run else 1
    if uncached and not args.yes and input("Call Prisma now? This spends Gnani credits [y/N] ").strip().lower() != "y":
        print("Stopped. Nothing was called.")
        return 1

    records = []
    for case, v, audio in jobs:
        rec = run_variant(case, v, audio, ctx)
        records.append(rec)
        status = rec.get("error") or (
            f"WER {rec['wer']:.0%}, items {sum(s['correct'] for s in rec['score']['items'])}/{len(case['expected'])}"
            f"{' (stt cached)' if rec.get('stt_cached') else ''}")
        print(f"  {case['id']} {v}: {status}")

    summaries = [aggregate(records, data["cases"], v, call_date) for v in variants]
    meta = {
        "run_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"), "cases": len(data["cases"]),
        "call_time": data["call_time"], "stt_model": settings.gnani_stt_model,
        "stt_format": settings.gnani_stt_format,
        "llm": settings.groq_model or settings.gemini_model or "not set",
    }
    args.out.write_text(render_markdown(meta, summaries, records, data["cases"]))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps({"meta": meta, "summaries": summaries, "records": records},
                                        ensure_ascii=False, indent=1, default=str))
    print(f"Wrote {args.out} and {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
