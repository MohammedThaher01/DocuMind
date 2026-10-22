"""Shared pytest fixtures.

The unit tests never touch the network: ``main.call_llm`` is always replaced by
``support.FakeLLM``, and generated documents are written to a temporary
directory instead of the repository's ``generated_docs`` folder.
"""
import pytest

import support
import main


@pytest.fixture(autouse=True)
def isolated_output_dir(tmp_path, monkeypatch):
    """Keep generated .docx files out of the repository."""
    out = tmp_path / "generated_docs"
    out.mkdir()
    monkeypatch.setattr(main, "OUTPUT_DIR", str(out))
    return out


@pytest.fixture
def fake_llm(monkeypatch):
    """Install a deterministic FakeLLM and return it."""
    def _install(**kwargs):
        return support.install_fake_llm(monkeypatch, support.FakeLLM(**kwargs))
    return _install


@pytest.fixture
def budget_email():
    return support.load_budget_email()
