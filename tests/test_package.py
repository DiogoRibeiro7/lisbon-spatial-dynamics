"""Basic package import test."""

from importlib import import_module


def test_package_imports() -> None:
    """The package should be importable."""
    module = import_module("lisbon_spatial_dynamics")
    assert module is not None
