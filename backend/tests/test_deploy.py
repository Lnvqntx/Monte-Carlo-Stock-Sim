"""Deployment config sanity checks (Vercel entrypoint, deps, Python pin, Render Blueprint)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _names(reqs: list[str]) -> set[str]:
    return {re.split(r"[<>=!~\[ ;]", r.strip(), maxsplit=1)[0].lower() for r in reqs if r.strip()}


def _requirements() -> list[str]:
    lines = (BACKEND / "requirements.txt").read_text().splitlines()
    return [ln.split("#", 1)[0].strip() for ln in lines if ln.split("#", 1)[0].strip()]


def test_vercel_entrypoint_exports_the_api_app():
    import index
    from api.main import app

    assert index.app is app


def test_pyproject_runtime_deps_match_requirements_txt():
    # Vercel may install from either file; both must list exactly the API runtime deps.
    pyproject = tomllib.loads((BACKEND / "pyproject.toml").read_text())
    assert sorted(pyproject["project"]["dependencies"]) == sorted(_requirements())


def test_runtime_deps_exclude_dev_only_packages():
    dev_only = {"rich", "matplotlib", "pytest", "httpx"}
    assert not dev_only & _names(_requirements())


def test_python_version_is_pinned_to_312():
    assert (BACKEND / ".python-version").read_text().strip() == "3.12"


def test_vercelignore_keeps_runtime_code_and_drops_tests():
    ignored = {ln.strip() for ln in (BACKEND / ".vercelignore").read_text().splitlines()
               if ln.strip() and not ln.startswith("#")}
    assert {"tests/", "output/", "requirements-dev.txt"} <= ignored
    for needed in ("index.py", "api/", "core/", "requirements.txt", "pyproject.toml",
                   ".python-version"):
        assert needed not in ignored


def test_render_blueprint_matches_api():
    text = (BACKEND / "render.yaml").read_text()
    assert "buildCommand: pip install -r requirements.txt" in text
    assert "startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT" in text
    assert "healthCheckPath: /api/health" in text
    assert "rootDir: backend" in text
