"""Installed commands must import and explain their arguments without source data."""

from __future__ import annotations

import sys
from importlib.metadata import EntryPoint, distribution

import pytest

_COMMANDS = tuple(
    entry
    for entry in distribution("lisbon-spatial-dynamics").entry_points
    if entry.group == "console_scripts"
)


@pytest.mark.parametrize("entry", _COMMANDS, ids=lambda entry: entry.name)
def test_installed_command_help(
    entry: EntryPoint, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", [entry.name, "--help"])

    with pytest.raises(SystemExit) as exit_info:
        entry.load()()

    assert exit_info.value.code == 0
    assert "usage:" in capsys.readouterr().out
