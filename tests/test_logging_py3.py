#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `logging_py3` package."""

import pytest

from click.testing import CliRunner

from logging_py3 import logging_py3
from logging_py3 import cli

def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert 'logging_py3.cli.main' in result.output
    help_result = runner.invoke(cli.main, ['--help'])
    assert help_result.exit_code == 0
    assert '--help  Show this message and exit.' in help_result.output

def test_setup_logging():
    # TODO setup default logging
    # TODO
    pass

def test_update_config():
    pass
    # TODO setup default logging
    # TODO Open a logging server
    # TODO Update the logging config
    # TODO Check the logging config
    # TODO Update the logging config to default
    # TODO Check the logging config again
