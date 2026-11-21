"""La versión: una sola fuente (src/rayacash/_version.py), que el README y el CHANGELOG repiten."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import rayacash
from rayacash._util import user_agent

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

# El CHANGELOG del tag v1.3.0 desde «## 1.3.0» hasta el final: lo que ya se publicó en PyPI (la
# 1.2.0, desde «## 1.2.0», tenía 38c4bd45702ba4808933d511411e2002f04c1d802ab60b8efe99c7754cbcce32,
# y la 1.1.0, desde «## 1.1.0», bdc7e9c16b7935aa9d6b8e98937c4f77c601d7ae1027a311acbcade0b0ea286f).
PUBLISHED_HISTORY_SHA256 = "359d39369e4d83bfe3c6861dca134cbc98f550c1ea23576711d51045e1fb3969"


def test_the_version_is_1_4_0() -> None:
    # La 1.3.0 ya está en PyPI: el Facturador sale como 1.4.0, nunca como otra 1.3.0.
    assert rayacash.VERSION == "1.4.0"
    assert rayacash.__version__ == rayacash.VERSION
    assert user_agent(None).startswith(f"rayacash-python/{rayacash.VERSION} Python/")


def test_the_readme_names_the_current_version() -> None:
    # El README es la página de PyPI.
    assert f"Versión {rayacash.VERSION}. Requiere Python 3.9" in README
    assert f"(`rayacash-python/{rayacash.VERSION} … mi-plugin/1.2.0`)" in README


def test_the_changelog_starts_with_the_current_version() -> None:
    versions = re.findall(r"^## (\S+)$", CHANGELOG, flags=re.MULTILINE)
    assert versions[:2] == [rayacash.VERSION, "1.3.0"]
    assert len(versions) == len(set(versions))


def test_the_published_history_never_changes() -> None:
    # Una versión publicada no se vuelve a publicar y su entrada cuenta lo que salió: de la 1.3.0
    # para atrás, el CHANGELOG es byte a byte el de los tags.
    published = CHANGELOG[CHANGELOG.index("\n## 1.3.0\n") + 1 :]
    assert hashlib.sha256(published.encode("utf-8")).hexdigest() == PUBLISHED_HISTORY_SHA256
