from typing import TYPE_CHECKING
from ..base.handler import BaseHandler

if TYPE_CHECKING:
    from ..fish_bowl import FishBowl

class SuperColliderHandler(BaseHandler):
    def __init__(self):
        self.env = None
        self.events = {
            'play': lambda: print('Playing something')
        }

    def setup(self, env: 'FishBowl'):
        self.env = env

    def hook(self, event: str, *args, **kwargs):
        pass