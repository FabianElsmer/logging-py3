# -*- coding: utf-8 -*-
"""Main module."""

import atexit
import logging
import logging.config
import socket
import os
import struct
import json

import yaml

DEFAULT_LOG_FORMAT = "{asctime} {levelname:3.3} {name}: {message}"
LOG = logging.getLogger(__name__)


def setup_logging(config: dict = None, listen_port=None) -> None:
    config = _get_config(config)

    _setup_logging(config)

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


def _setup_logging(config) -> None:
        logging.config.dictConfig(config)


def listen(listen_port=None, verify: function = None):
    LOG.warning(('---SECURITY NOTICE---\n',
                 'Never listen for config changes ',
                 'on machines with untrusted users!\n',
                 'See: https://docs.python.org/3/library/logging.config.html',
                 '#logging.config.listen'))

    # create and start listener on port
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


def stop_listen(config_change_listener):
    logging.config.stopListening()
    config_change_listener.join()


def update_config(path_or_json=None,
                  incremental=True,
                  listen_port=logging.config.DEFAULT_LOGGING_CONFIG_PORT):
    config = _get_config(path_or_json)

    # Don't overwrite full config by default
    config.setdefault('incremental', incremental)

    data_to_send = json.dumps(config)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', listen_port))
    s.send(struct.pack('>L', len(data_to_send)))
    s.send(data_to_send)
    s.close()


def _get_config(path_or_dict=None):
    """ Loads a yaml/json file, or python dict """

    if path_or_dict is None:
        path_or_dict = os.environ.get('LOG_CONFIG', None)

    config = {}
    if isinstance(path_or_dict, dict):
        config = path_or_dict

    elif os.path.exists(path_or_dict):
        with open(path_or_dict) as f:
            data = f.read()

            # Can load both yaml and json files
            config = yaml.safe_load(data)

    elif path_or_dict is not None:
        raise ValueError(('Config could not be loaded: ',
                          str(path_or_dict)))
    else:
        LOG.info('Using default logging config')

    # always need a default formatter, handler and logger
    config.setdefault('formatters', {})
    config.setdefault('handlers', {})
    config.setdefault('loggers', {})

    default_log_format = config.pop('default_log_format',
                                    DEFAULT_LOG_FORMAT)
    default_log_level = config.pop('default_log_level', 'DEBUG')

    default_formatter = {
        'format': default_log_format,
        'class': 'colored_formatter.ColoredFormatter',
        'style': '{',
    }

    default_handler = {
        'level': 'DEBUG',
        'class': 'logging.StreamHandler',
        'formatter': 'default',
    }

    default_handlers = [handler for handler in config['handlers'].keys() if
                        config['handlers'][handler] is not None]

    default_logger = {'level': default_log_level,
                      'handlers': default_handlers}

    config['formatters'].setdefault('default', default_formatter)

    # logging to console can be disabled by setting the console handler to None
    config['handlers'].setdefault('console', default_handler)

    # set the global root logger config
    config['loggers'].setdefault('', default_logger)

    return config
