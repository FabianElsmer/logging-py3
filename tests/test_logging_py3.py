#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `logging_py3` package."""
import os
from copy import deepcopy
import sys
import asyncio
import logging
import importlib
import yaml

import pytest

from click.testing import CliRunner
from logging_py3 import cli
from logging_py3 import log

TEST_CONFIG = {
    'handlers': {
        'test_handler': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'test_formatter',
            'stream': 'ext://sys.stdout'
        }
    },
    'formatters': {
        'test_formatter': {
            'format': "TestFormatter: {asctime} {levelname:3.3} {name}: {message}",
            'class': 'logging_py3.colored_formatter.ColoredFormatter',
            'style': '{',
        }

    },
    'loggers': {
        'root': {
            'level': 'INFO',
            'handlers': ['test_handler']
        }
    },
    'show_warnings': False
}

BASE_PATH = os.path.dirname(os.path.realpath(__file__))


def reset_logging_module():
    """ Logging module is shared globally
        It should be reset before every test
    """
    logging.shutdown()
    importlib.reload(logging)
    importlib.reload(log)


def fullname(o):
    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__
    return module + '.' + o.__class__.__name__


def check_log_level(level, capsys, logger='root'):
    if isinstance(logger, str):
        logger = logging.getLogger(logger)

    log_order = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    index = log_order.index(level)

    to_log = log_order[index:]
    to_ignore = log_order[:index]

    # Clear the previous logs
    capsys.readouterr()

    for level in log_order:
        log_func = getattr(logger, level.lower())
        log_func(level)

    output = capsys.readouterr()

    for level in to_log:
        assert level in output.out

    for level in to_ignore:
        assert level not in output.out

def check_logging_config(config_dict, incremental=False):
    manager = logging.Logger.manager

    # TODO When checking incremental
    # TODO Keys can be missing, like all loggers, handlers
    # Check every logger
    for logger, logger_cfg in config_dict['loggers'].items():
        assert logger in manager.loggerDict
        logger_obj = manager.loggerDict[logger]

        assert logger_obj.level == logging._nameToLevel[logger_cfg['level']]

        # Check every loggers handler
        for handler in logger_cfg['handlers']:
            handler_cfg = config_dict['handlers'].get(handler)
            assert handler_cfg is not None

            assert handler in logging._handlers
            handler_obj = logging._handlers[handler]

            handler_added = list(filter(lambda x: x == handler_obj, logger_obj.handlers))
            assert len(handler_added) == 1
            handler_added = handler_added[0]
            assert handler_added.level == logging._nameToLevel[handler_cfg['level']]

            # Check every handlers formatter
            formatter_cfg = config_dict['formatters'][handler_cfg['formatter']]
            assert fullname(handler_added.formatter) == formatter_cfg['class']



# def test_command_line_interface():
#     """Test the CLI."""
#     runner = CliRunner()
#     result = runner.invoke(cli.main)
#     assert result.exit_code == 0
#     assert 'logging_py3.cli.main' in result.output
#     help_result = runner.invoke(cli.main, ['--help'])
#     assert help_result.exit_code == 0
#     assert '--help  Show this message and exit.' in help_result.output


def test_setup_logging_default(capsys):
    reset_logging_module()

    log.setup_logging()

    default_config = log._get_config()

    assert len(default_config['loggers'].keys()) > 0
    assert len(default_config['handlers'].keys()) > 0
    assert len(default_config['formatters'].keys()) > 0

    check_logging_config(default_config)
    check_log_level('DEBUG', capsys)


def test_setup_logging_dict(capsys):
    reset_logging_module()

    log.setup_logging(TEST_CONFIG)

    check_logging_config(TEST_CONFIG)

    check_log_level('INFO', capsys)



def test_setup_logging_path_yml(capsys):
    reset_logging_module()

    config_path = os.path.join(BASE_PATH, 'test_config.yml')
    log.setup_logging(config_path)

    with open(config_path) as f:
        data = f.read()
        config_dict = yaml.safe_load(data)

    check_logging_config(config_dict)

    check_log_level('INFO', capsys)



def test_setup_logging_path_json(capsys):
    reset_logging_module()

    config_path = os.path.join(BASE_PATH, 'test_config.json')
    log.setup_logging(config_path)

    with open(config_path) as f:
        data = f.read()
        config_dict = yaml.safe_load(data)

    check_logging_config(config_dict)

    check_log_level('INFO', capsys)

@pytest.mark.asyncio
async def test_update_config(capsys):
    reset_logging_module()

    log.setup_logging(TEST_CONFIG)
    check_logging_config(TEST_CONFIG)
    check_log_level('INFO', capsys)

    listener = log.listen()

    # Give the listener thread a second to start
    await asyncio.sleep(1)

    updated_log_level = 'CRITICAL'
    config_update = {
        'incremental': True,
        'loggers': {
            'root': {
                'level': updated_log_level,
            }
        },
        'handlers': {
            'test_handler': {
                'level': updated_log_level
            }
        }
    }

    log.update_config(config_update)

    updated_config = deepcopy(TEST_CONFIG)
    updated_config['loggers']['root'].update(config_update['loggers']['root'])
    updated_config['handlers']['test_handler'].update(config_update['handlers']['test_handler'])

    # Give the listener thread a second to process
    await asyncio.sleep(1)
    check_logging_config(updated_config)
    check_log_level(updated_log_level, capsys)

    updated_config = deepcopy(TEST_CONFIG)
    updated_config['incremental'] = False
    log.update_config(updated_config)

    # Give the listener thread a second to process
    await asyncio.sleep(1)
    check_logging_config(updated_config)
    check_log_level('INFO', capsys)

    log.stop_listen(listener)

def test_sentry():
    reset_logging_module()

    config = {
        'sentry_config': {
            # Sentry IO project for this repo
            'dsn': 'https://3e07eb5ace2546ed815dd3680e480a36@sentry.io/1536083',
            'environment': 'localTest'
        }
    }

    log.setup_logging(config)

    # TODO Check that a sentry handler has been added

def test_disable_existing_loggers(capsys):
    reset_logging_module()


    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logger = logging.getLogger('pytest_debug')

    check_log_level('INFO', capsys, logger)

    log.setup_logging({'disable_existing_loggers': False})

    check_log_level('INFO', capsys, logger)


