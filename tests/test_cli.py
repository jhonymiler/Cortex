"""Tests for the cortext-memory CLI helpers."""

from cortext.cli import _set_provider_in_yaml


def _write(tmp_path, text):
    (tmp_path / "config.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def _read(tmp_path):
    return (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_set_provider_only_touches_memory_block(tmp_path):
    # A `provider:` under `model:` must NOT be changed (regression: the setter
    # used to rewrite the first provider: anywhere, corrupting model.provider).
    cfg = (
        "model:\n"
        "  default: minimax/minimax-m3\n"
        "  provider: openrouter\n"
        "memory:\n"
        "  memory_enabled: false\n"
        "  provider: builtin\n"
        "  cortext:\n"
        "    namespace: hermes\n"
        "delegation:\n"
        "  model: x\n"
    )
    _write(tmp_path, cfg)
    assert _set_provider_in_yaml(tmp_path) is True
    out = _read(tmp_path)
    assert "  provider: openrouter\n" in out      # model.provider untouched
    assert "  provider: cortext\n" in out          # memory.provider switched
    assert out.count("provider: cortext") == 1


def test_set_provider_inserts_when_missing(tmp_path):
    cfg = "memory:\n  memory_enabled: false\nother:\n  x: 1\n"
    _write(tmp_path, cfg)
    assert _set_provider_in_yaml(tmp_path) is True
    out = _read(tmp_path)
    assert "provider: cortext" in out
    assert "other:\n  x: 1" in out                 # other sections intact


def test_set_provider_no_config_is_safe(tmp_path):
    assert _set_provider_in_yaml(tmp_path) is False
