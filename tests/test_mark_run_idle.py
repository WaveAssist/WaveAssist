import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import waveassist


def test_mark_run_idle_writes_run_scoped_flag(monkeypatch):
    """mark_run_idle() must write the 'run_idle' key, run-based, as a string '1' — like display_output."""
    captured = {}

    def fake_store(key, data, **kw):
        captured["key"] = key
        captured["data"] = data
        captured["kw"] = kw
        return True

    monkeypatch.setattr(waveassist, "store_data", fake_store)
    assert waveassist.mark_run_idle() is True
    assert captured["key"] == "run_idle"
    assert captured["data"] == "1"
    assert captured["kw"].get("run_based") is True
    assert captured["kw"].get("data_type") == "string"


def test_mark_run_idle_is_exported():
    assert hasattr(waveassist, "mark_run_idle")
    assert "mark_run_idle" in waveassist.__all__


def test_mark_run_idle_propagates_failure(monkeypatch):
    monkeypatch.setattr(waveassist, "store_data", lambda *a, **k: False)
    assert waveassist.mark_run_idle() is False
