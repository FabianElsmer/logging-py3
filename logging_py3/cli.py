"""Console script for logging_py3."""
import os
import sys
import click
import logging

from logging_py3 import log

LOG = logging.getLogger(__name__)

@click.group()
def cli():
    pass

@cli.command()
@click.option('--config', '-c', help='Path to a config file or json data of a config file')
@click.option('--overwrite', '-o', is_flag=True, help='Overwriting existing loggers and handles instead of updating existing ones')
@click.option('--port', '-p', help='Port to send config changes to')
def update_config(config, overwrite, port):

    incremental = not overwrite
    log.update_config(config, incremental, port, True)


