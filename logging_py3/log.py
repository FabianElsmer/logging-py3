# -*- coding: utf-8 -*-
"""Main module."""

import atexit
import json
import logging
import logging.config
import socket
import sys

import os
import struct
import warnings
import yaml
from logging_py3 import tracing

DEFAULT_LOG_FORMAT = "{asctime} {levelname:3.3} {name}: {message}"
LOG = logging.getLogger(__name__)


def setup_logging(config: dict = None) -> None:
    config = _get_config(config)

    _setup_logging(config)


def _setup_logging(config) -> None:
    show_warnings = config.pop('show_warnings', True)
    sentry_config = config.pop('sentry_config', None)
    tracemalloc = config.pop('tracemalloc', None)
    listen_port = config.pop('listen', None)

    logging.config.dictConfig(config)

    # Turn on warnings
    if show_warnings and not sys.warnoptions:
        warnings.simplefilter("always")

    # Configure sentry
    if sentry_config:
        _setup_sentry(sentry_config)

    if tracemalloc:
        tracing.start()

    # Security Notice
    # ===============
    #
    # Portions of the configuration are passed through eval()
    # use of this function may open its users to a security risk.
    # If the process calling listen() runs on a multi-user machine
    # where users cannot trust each other, then a malicious user
    # could arrange to run arbitrary code in a victim user’s process
    if listen_port is not None:
        listen(listen_port)


def _setup_sentry(sentry_config):
    if sentry_config:
        # Optional sentry integration
        import sentry_sdk
        from sentry_sdk.integrations.excepthook import ExcepthookIntegration

        if 'dsn' not in sentry_config:
            raise ValueError('No value for sentry dsn configured')

        dsn = sentry_config.get('dsn')
        environment = sentry_config.get('environment')

        exception_hook = ExcepthookIntegration(always_run=True)
        sentry_sdk.init(
            dsn=dsn, environment=environment, integrations=[exception_hook])


def listen(listen_port=None, verify=None):
    LOG.warning(('---SECURITY NOTICE---\n',
                 'Never listen for config changes ',
                 'on machines with untrusted users!\n',
                 'See: https://docs.python.org/3/library/logging.config.html',
                 '#logging.config.listen'))

    # create and start listener on port
    # TODO use verify to enable/disable tracemalloc and warnings?
    listen_kwargs = {
        'verify': verify,
        'port': logging.config.DEFAULT_LOGGING_CONFIG_PORT
    }

    if isinstance(listen_port, int):
        listen_kwargs['port'] = listen_port

    config_change_listener = logging.config.listen(**listen_kwargs)
    config_change_listener.start()

    LOG.info('Listening for config changes on port: {port}',
             port=listen_kwargs["port"])

    atexit.register(stop_listen, config_change_listener)

    return config_change_listener


def stop_listen(config_change_listener):
    logging.config.stopListening()
    config_change_listener.join()


def update_config(path_or_json=None,
                  incremental=True,
                  listen_port=None,
                  explicit_disable=False):
    config = _get_config(path_or_json)

    # Custom port > config port > default port
    cfg_port = config.pop('listen', logging.config.DEFAULT_LOGGING_CONFIG_PORT)
    listen_port = listen_port or cfg_port

    # Don't overwrite full config by default
    config.setdefault('incremental', incremental)

    dangerous = not config['incremental'] and config['disable_existing_loggers']
    if dangerous and explicit_disable:
        success = _query_yes_no('The configuration you chose could delete, disable or break existing loggers and handlers! (until application restart)\nAre you sure to force this config?')
        if not success:
            return

    data_to_send = json.dumps(config)
    data_to_send = data_to_send.encode('utf-8')

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', listen_port))
    s.send(struct.pack('>L', len(data_to_send)))
    s.send(data_to_send)
    s.close()


def _get_config(path_or_dict=None):
    """ Loads a yaml/json file, yaml/json string or python dict """

    if path_or_dict is None:
        path_or_dict = os.environ.get('LOG_CONFIG', None)

    config = {}
    if isinstance(path_or_dict, dict):
        config = path_or_dict

    elif isinstance(path_or_dict, str):
        if os.path.exists(path_or_dict):
            with open(path_or_dict) as f:
                path_or_dict = f.read()

        # Can load both yaml and json files
        config = yaml.safe_load(path_or_dict)

        if not isinstance(config, dict):
            raise ValueError('An invalid json/yaml config was supplied')

    elif path_or_dict is not None:
        raise ValueError(('Config could not be loaded: ',
                          str(path_or_dict)))
    else:
        LOG.info('Using default logging config')

    config.setdefault('version', 1)

    # Prevents loggers created before configuration to be disabled
    # All active handlers will be removed though
    config.setdefault('disable_existing_loggers', False)

    # always need a default formatter, handler and logger
    config.setdefault('formatters', {})
    config.setdefault('handlers', {})
    config.setdefault('loggers', {})

    default_log_format = config.pop('default_log_format',
                                    DEFAULT_LOG_FORMAT)
    default_log_level = config.pop('default_log_level', 'DEBUG')

    default_formatter = {
        'format': default_log_format,
        'class': 'logging_py3.colored_formatter.ColoredFormatter',
        'style': '{',
    }

    default_handler = {
        'level': 'DEBUG',
        'class': 'logging.StreamHandler',
        'formatter': 'default',
        'stream': 'ext://sys.stdout'
    }

    # logging to console can be disabled by setting the console handler to None
    config['handlers'].setdefault('console', default_handler)

    default_handlers = [handler for handler in config['handlers'].keys() if
                        config['handlers'][handler] is not None]

    default_logger = {'level': default_log_level,
                      'handlers': default_handlers}

    config['formatters'].setdefault('default', default_formatter)

    # set the global root logger config
    registered_loggers = config['loggers'].keys()
    if not ('' in registered_loggers or 'root' in registered_loggers):
        config['loggers'].setdefault('root', default_logger)

    config.setdefault('show_warnings', True)

    return config


def _query_yes_no(question, default="no"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")
