from __future__ import with_statement
import asyncio
import pathlib
import warnings
from typing import Union

from rich import print
from rich.console import Console
from rich.markdown import Markdown
try:
    import uvloop
except ImportError:
    warnings.warn('uvloop is not installed, rhythm accuracy may be impacted')
else:
    uvloop.install()

from .clock.Clock import Clock
from .superdirt.Sound import Sound as S
from .superdirt.AutoBoot import (
        SuperColliderProcess,
        find_startup_file,
        find_synth_directory)
from .io.Osc import Client as OSC

warnings.filterwarnings("ignore")

def print_pre_alpha_todo() -> None:
    """ Print the TODOlist from pre-alpha version """
    cur_path = pathlib.Path(__file__).parent.resolve()
    with open("".join([str(cur_path), "/todo.md"])) as f:
        console = Console()
        console.print(Markdown(f.read()))


sardine = """

░██████╗░█████╗░██████╗░██████╗░██╗███╗░░██╗███████╗
██╔════╝██╔══██╗██╔══██╗██╔══██╗██║████╗░██║██╔════╝
╚█████╗░███████║██████╔╝██║░░██║██║██╔██╗██║█████╗░░
░╚═══██╗██╔══██║██╔══██╗██║░░██║██║██║╚████║██╔══╝░░
██████╔╝██║░░██║██║░░██║██████╔╝██║██║░╚███║███████╗
╚═════╝░╚═╝░░╚═╝╚═╝░░╚═╝╚═════╝░╚═╝╚═╝░░╚══╝╚══════╝

Sardine is a small MIDI/OSC sequencer made for live-
coding. Check the examples/ folder to learn more. :)
"""


# Pretty printing
print(f"[red]{sardine}[/red]")
print_pre_alpha_todo()
print('\n')

c = Clock()
cs = c.schedule
cr = c.remove

# Exposing some MIDI functions
def note(delay, note: int=60, velocity: int =127, channel: int=1):
    """ Send a MIDI Note """
    asyncio.create_task(c._midi.note(
        clock=c, delay=delay, note=note,
            velocity=velocity, channel=channel))

def cc(value=60, control=127, channel=1):
    """ Send a MIDI Note """
    asyncio.create_task(
            c._midi.control_change(value=value,
                control=control, channel=channel))

asyncio.create_task(c._send_start(initial=True))

# Should start, doesn't start
SC = SuperColliderProcess(
        synth_directory=find_synth_directory(),
        startup_file=find_startup_file())

def swim(fn):
    """ Push a function to the clock """
    cs(fn)
    return fn

def die(fn):
    """ Remove a function from the clock """
    cr(fn)
    return fn

async def nap(duration):
    """ Musical sleep inside coroutines """
    duration = c.tick_time + (duration * c.ppqn)
    while c.tick_time < duration:
        await asyncio.sleep(c._get_tick_duration() / c.ppqn)

async def sync():
    """ Manual resynchronisation """
    cur_bar = c.elapsed_bars
    while c.phase != 1 and c.elapsed_bars != cur_bar + 1:
        await asyncio.sleep(c._get_tick_duration() / c.ppqn)

# Tests

my_osc = OSC(ip="127.0.0.1",
        port= 23000, name="Bibu",
        ahead_amount=0.25)

# @swim
# async def bd(delay=1):
#     S('bd').out()
#     my_osc.send('/hello', [123, 245])
#     cs(bd, delay=1)


@swim
async def one(delay=1):
    note(1, 60, 127, 1)
    cs(one, delay=1)

@swim
async def two(delay=0.5):
    note(1, 67, 127, 1)
    cs(one, delay=0.5)
