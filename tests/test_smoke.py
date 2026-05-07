"""Smoke test: package is importable and version is sane."""
from __future__ import annotations


def test_package_importable():
    import emoekg

    assert hasattr(emoekg, "__version__")


def test_version_is_semver_like():
    from emoekg import __version__

    parts = __version__.split(".")
    assert len(parts) == 3, f"expected X.Y.Z, got {__version__!r}"
    for p in parts:
        assert p.isdigit(), f"non-numeric segment: {p!r}"
