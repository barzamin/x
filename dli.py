#!/usr/bin/env python3
import os
import requests
import click
from configparser import ConfigParser
from urllib.parse import urlunparse, ParseResult
from requests.auth import HTTPDigestAuth
from pathlib import Path
from dataclasses import dataclass
from rich import print as rprint, inspect
from rich.table import Table

class DLIPDU:
    def __init__(self, host, auth):
        self.s = requests.Session()
        self.s.auth = auth
        self.s.headers = {
            'X-CSRF': 'X',
        }

        self.host = host

    def _pathto(self, endpoint):
        return urlunparse(ParseResult(scheme='http', netloc=self.host, path=endpoint, params=None, query=None, fragment=None))

    def on(self, outlet_idx: int):
        self.set_state(outlet_idx, True)

    def off(self, outlet_idx: int):
        self.set_state(outlet_idx, True)

    def set_state(self, outlet_idx: int, state: bool):
        r = self.s.put(self._pathto(f'/restapi/relay/outlets/{outlet_idx}/state/'), json=state)
        r.raise_for_status()

    def cycle(self, outlet_idx: int):
        r = self.s.post(self._pathto(f'/restapi/relay/outlets/{outlet_idx}/cycle/'))
        r.raise_for_status()

    def configured_state(self, outlet_idx: int):
        r = self.s.get(self._pathto(f'/restapi/relay/outlets/{outlet_idx}/state/'))
        return r.json()

    def physical_state(self, outlet_idx: int):
        r = self.s.get(self._pathto(f'/restapi/relay/outlets/{outlet_idx}/physical_state/'))
        return r.json()

    def outlets(self):
        r = self.s.get(self._pathto(f'/restapi/relay/outlets/'))
        return r.json()

    def _outlet2idx(self, outlet):
        try:
            return int(outlet)
        except ValueError:
            # find outlet with this name
            outlets = self.outlets()
            for i, o in enumerate(outlets):
                if o['name'] == outlet:
                    return i
            raise KeyError(f'no outlet called `{outlet}` exists')


@dataclass
class CliCtx:
    pdu: DLIPDU = None

def default_config() -> Path:
    confdir = os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
    return confdir / 'dli.cfg'

@click.group()
@click.argument('pduname')
@click.option('--config-path', type=click.Path(), default=default_config, show_default='$XDG_CONFIG_HOME/dli.cfg')
@click.pass_context
def cli(ctx, pduname, config_path):
    """
    A simple tool to interact with Digital Loggers PDUs.
    """
    ctx.ensure_object(CliCtx)

    config = ConfigParser()
    config.read(config_path)

    ctx.obj.pdu = DLIPDU(config[pduname]['host'], HTTPDigestAuth(config[pduname]['username'], config[pduname]['password']))

@cli.command()
@click.argument('outlet')
@click.argument('state', type=click.Choice(['off', 'on']))
@click.pass_context
def set(ctx, outlet, state):
    """
    Set an outlet's state.
    """
    ctx.obj.pdu.set_state(ctx.obj.pdu._outlet2idx(outlet), state == 'on')

@cli.command()
@click.argument('outlet')
@click.pass_context
def cycle(ctx, outlet):
    """
    Cycle an outlet.
    """
    ctx.obj.pdu.cycle(ctx.obj.pdu._outlet2idx(outlet))

@cli.group()
def get():
    """
    Query the state of outlets.
    """

@get.command()
@click.argument('outlet')
@click.pass_context
def configured(ctx, outlet):
    """
    Query the "configured" state of an outlet (the setpoint).
    """
    print(ctx.obj.pdu.configured_state(ctx.obj.pdu._outlet2idx(outlet)))

@get.command()
@click.argument('outlet')
@click.pass_context
def physical(ctx, outlet):
    """
    Query the physical state of an outlet.
    """
    print(ctx.obj.pdu.physical_state(ctx.obj.pdu._outlet2idx(outlet)))

def _on(x):
    return 'on' if x else 'off'

@cli.command()
@click.pass_context
def outlets(ctx):
    """
    List a table of outlets known to the PDU, and their states.
    """
    table = Table()
    table.add_column('idx')
    table.add_column('name')
    table.add_column('configured')
    table.add_column('physical')
    table.add_column('cycle Δt')
    for i, outlet in enumerate(ctx.obj.pdu.outlets()):
        table.add_row(str(i), outlet['name'], _on(outlet['state']), _on(outlet['physical_state']), str(outlet['cycle_delay'] or '〜'))

    rprint(table)

if __name__ == '__main__':
    cli()
