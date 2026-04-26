import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_app_web_master import _normalize_gradio_debug_env


def test_normalize_gradio_debug_env_coerces_booleanish_values(monkeypatch):
    monkeypatch.setenv("GRADIO_DEBUG", "true")
    _normalize_gradio_debug_env()
    assert os.environ["GRADIO_DEBUG"] == "1"

    monkeypatch.setenv("GRADIO_DEBUG", "false")
    _normalize_gradio_debug_env()
    assert os.environ["GRADIO_DEBUG"] == "0"


def test_normalize_gradio_debug_env_falls_back_to_safe_zero(monkeypatch):
    monkeypatch.setenv("GRADIO_DEBUG", "definitely-not-an-int")
    _normalize_gradio_debug_env()
    assert os.environ["GRADIO_DEBUG"] == "0"
