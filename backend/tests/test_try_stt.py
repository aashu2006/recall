import pytest

from app.config import Settings
from scripts import try_stt


def test_flags_override_settings_for_this_run_only():
    base = Settings(_env_file=None)
    args = try_stt.parse_args(
        ["note.ogg", "--model", "prisma-v2.5", "--format", "transcribe", "--language", "hi-IN"]
    )

    run = try_stt.apply_overrides(base, args)

    assert (run.gnani_stt_model, run.gnani_stt_format, run.gnani_stt_language_code) == (
        "prisma-v2.5",
        "transcribe",
        "hi-IN",
    )
    assert (base.gnani_stt_model, base.gnani_stt_format, base.gnani_stt_language_code) == (
        "prisma-v3.0",
        "codemix",
        "hi-IN,en-IN",
    )


def test_no_flags_keep_settings():
    base = Settings(_env_file=None)

    assert try_stt.apply_overrides(base, try_stt.parse_args(["note.ogg"])) == base


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("none", []),
        ("NONE", []),
        ("MS sheet, bracket,,kg ", ["MS sheet", "bracket", "kg"]),
    ],
)
def test_parse_keyterms(value, expected):
    assert try_stt.parse_keyterms(value) == expected


def test_main_passes_overrides_to_transcribe(monkeypatch, capsys):
    seen = {}

    def fake_transcribe(audio_path, *, settings, keyterms):
        seen.update(audio=audio_path, model=settings.gnani_stt_model, keyterms=keyterms)
        return {"transcript": "", "segments": [], "model": settings.gnani_stt_model}

    monkeypatch.setattr(try_stt, "get_settings", lambda: Settings(_env_file=None, gnani_api_key="k"))
    monkeypatch.setattr(try_stt.stt, "transcribe", fake_transcribe)

    try_stt.main(["note.ogg", "--model", "prisma-v2.5", "--keyterms", "none"])

    assert seen == {"audio": "note.ogg", "model": "prisma-v2.5", "keyterms": []}
    assert '"model": "prisma-v2.5"' in capsys.readouterr().out
