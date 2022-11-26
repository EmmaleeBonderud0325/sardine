from abc import ABC, abstractmethod
import asyncio
from typing import Optional, Union

from .handler import BaseHandler

__all__ = ("BaseClock",)

def _round_float(n: float, prec: int = 3):
    s = format(n, f".{prec}f")
    return s.rstrip("0").rstrip(".")


class BaseClock(BaseHandler, ABC):
    """The base for all clocks to inherit from.

    This interface expects clocks to manage its own source of time
    and provide the `phase`, `beat`, and `tempo` properties.

    In addition, an optional `async sleep()` method can be defined
    to provide a mechanism for sleeping a specified duration.
    If this method is not defined, the `FishBowl.sleeper` instance
    will use a built-in polling mechanism for sleeping.
    """

    def __init__(self):
        super().__init__()
        self._run_task: Optional[asyncio.Task] = None
        self._time_is_origin: bool = True

    def __repr__(self) -> str:
        status = "running" if self.is_running() else "stopped"
        return (
            "<{name} {status} time={0.time:.1f}"
            " tempo={tempo} beats_per_bar={0.beats_per_bar}>"
        ).format(
            self,
            name=type(self).__name__,
            status=status,
            tempo=_round_float(self.tempo),
        )

    def __str__(self) -> str:
        return (
            "({name} {0.time:.1f}s) -> [{tempo}|{beat}/{bar} {phase:.0%}]"
        ).format(
            self,
            name=type(self).__name__,
            tempo=_round_float(self.tempo, 3),
            beat=self.beat % self.beats_per_bar + 1,
            bar=self.beats_per_bar,
            phase=self.phase / self.beat_duration,
        )

    # Abstract methods

    @abstractmethod
    async def run(self):
        """The main run loop of the clock.

        This should setup any external time source, assign the current
        time to `internal_origin`, and then continuously
        update the `internal_time`.
        """

    @property
    @abstractmethod
    def bar(self) -> int:
        """The bar of the clock's current time.

        This property should account for time shift.
        """

    @property
    @abstractmethod
    def beat(self) -> int:
        """The beat of the clock's current time.

        This property should account for time shift.
        """

    @property
    @abstractmethod
    def beat_duration(self) -> float:
        """The length of a single beat in seconds.

        Typically this is represented as the function `60 / tempo`.
        """

    @property
    @abstractmethod
    def beats_per_bar(self) -> int:
        """The number of beats in each bar."""

    @property
    @abstractmethod
    def internal_origin(self) -> Optional[float]:
        """The clock's internal time origin if available, measured in seconds.

        At the start of the `run()` method, this should be set as early
        as possible in order for the `time` property to compute the
        elapsed time.

        This **must** support a setter as the base clock will automatically
        set this to the `internal_time` when the fish bowl is resumed.
        """

    @property
    @abstractmethod
    def internal_time(self) -> Optional[float]:
        """The clock's internal time if available, measured in seconds.

        This attribute should be continuously updated when the
        clock starts so the `time` property is able to move forward.
        """

    @property
    @abstractmethod
    def phase(self) -> float:
        """The phase of the current beat in the range `[0, beat_duration)`.

        This property should account for time shift.
        """

    @property
    @abstractmethod
    def tempo(self) -> float:
        """The clock's current tempo."""

    # Properties

    @property
    def shifted_time(self) -> float:
        """A shorthand for the current time with `Time.shift` added.

        Only the clock is expected to use this property when calculating
        the current phase/beat/bar.
        """
        return self.time + self.env.time.shift

    @property
    def time(self) -> float:
        """Returns the current time of the fish bowl.

        This uses the `internal_time` and `internal_origin` attributes
        along with the fish bowl's `Time.origin` to calculate a monotonic
        time for the entire system.

        This number will also add any `Time.shift` that has been applied.

        If the fish bowl has been paused or stopped, `Time.origin` will be set
        to the latest value provided by `internal_time`, and this property
        will return `Time.origin` until the fish bowl resumes or starts again.

        If either the `internal_time` or `internal_origin` attributes
        are not available, i.e. been set to `None`, this will default
        to the `Time.origin` (still including time shift). This should
        ideally be avoided when the clock starts running so time can
        flow as soon as possible.
        """
        if self._time_is_origin:
            return self.env.time.origin

        i_time, i_origin = self.internal_time, self.internal_origin
        if i_time is None or i_origin is None:
            return self.env.time.origin

        return i_time - i_origin + self.env.time.origin

    # Public methods

    def can_sleep(self) -> bool:
        """Checks if the clock supports sleeping."""
        # Get the sleep attribute and if it is a bound method, unwrap it
        # for the actual function
        method = getattr(self, "sleep", None)
        method = getattr(method, "__func__", method)
        return method is not BaseClock.sleep

    def get_beat_time(self, n_beats: Union[int, float], *, sync: bool = True) -> float:
        """Determines the amount of time to wait for N beats to pass.

        Args:
            n_beats (Union[int, float]): The number of beats to wait for.
            sync (bool):
                If True, the duration will be synchronized to an interval
                accounting for the current time (and influenced by time shift).
                If False, no synchronization is done, meaning the duration
                for a given beat and tempo will always be the same.

        Returns:
            float: The amount of time to wait in seconds.
        """
        interval = self.beat_duration * n_beats
        if interval <= 0.0:
            return 0.0
        elif not sync:
            return interval

        return interval - self.shifted_time % interval

    def get_bar_time(self, n_bars: Union[int, float], *, sync: bool = True) -> float:
        """Determines the amount of time to wait for N bars to pass.

        Args:
            n_bars (Union[int, float]): The number of bars to wait for.
            sync (bool):
                If True, the duration will be synchronized to an interval
                accounting for the current time (and influenced by time shift).
                If False, no synchronization is done, meaning the duration
                for a given bar and tempo will always be the same.

        Returns:
            float: The amount of time to wait in seconds.

        """
        return self.get_beat_time(n_bars * self.beats_per_bar, sync=sync)

    def is_running(self) -> bool:
        """Indicates if an asyncio task is currently executing `run()`."""
        return self._run_task is not None and not self._run_task.done()

    async def sleep(self, duration: Union[float, int]) -> None:
        """Sleeps for the given duration.

        This method can be optionally overridden by subclasses.
        If it is not overridden, it is assumed that the class
        does not support sleeping.

        Any implementations of this sleep must be able to handle
        `asyncio.CancelledError` on any asynchronous statements.
        """
        raise NotImplementedError

    # Protected methods

    def _dispatch_tempo_update(self, old: float, new: float):
        """Dispatches a `tempo_update` event if the old and new tempos changed.

        Subclasses are expected to always call this method
        after a new tempo is set.
        """
        if self.env is not None and old != new:
            self.env.dispatch("tempo_update", old, new)

    # Handler hooks

    def setup(self):
        for event in ("start", "pause", "resume", "stop"):
            self.register(event)

    def teardown(self):
        if self.is_running():
            self._run_task.cancel()

    def hook(self, event: str, *args):
        if event in ("start", "resume"):
            if not self.is_running():
                self._run_task = asyncio.create_task(self.run())

            # Setting internal origin here is only useful for the resume event,
            # unless the clock is able to provide an internal time before
            # the clock has started
            self.internal_origin = self.internal_time
            self._time_is_origin = False
        elif event == "pause":
            self.env.time.origin = self.time
            self._time_is_origin = True
        elif event == "stop":
            self.env.time.origin = self.time
            self._time_is_origin = True
            self.teardown()
        # print(f"{event=} {self.env.time.origin=} {self.time=} "
        #       f"{self.env.is_paused()=} {self.env.is_running()=}")
