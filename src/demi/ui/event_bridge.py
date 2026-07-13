"""Thread-safe delivery of worker events to the GUI main thread."""

from _queue import Empty
from collections.abc import Callable
from queue import SimpleQueue
from threading import get_ident


class MainThreadEventBridge[EventT]:
    """Queue worker events until the creating thread drains them.

    The bridge deliberately does not know controller event types. The
    composition root supplies a consumer on the pyglet main thread.
    """

    def __init__(self) -> None:
        """Create an empty bridge bound to the current thread."""
        self._main_thread_id = get_ident()
        self._events: SimpleQueue[EventT] = SimpleQueue()

    def emit(self, event: EventT) -> None:
        """Queue one event from any thread without invoking GUI code.

        Args:
            event: Immutable worker event to deliver later.
        """
        self._events.put(event)

    def drain(
        self,
        consume: Callable[[EventT], None],
        *,
        max_events: int = 64,
    ) -> int:
        """Deliver queued events in FIFO order on the creating thread.

        Args:
            consume: Main-thread event reducer.
            max_events: Maximum number of events to deliver in one GUI tick.

        Returns:
            Number of events delivered.

        Raises:
            RuntimeError: The caller is not the thread that created the bridge.
            ValueError: ``max_events`` is not positive.
        """
        if get_ident() != self._main_thread_id:
            raise RuntimeError
        if max_events < 1:
            raise ValueError
        delivered = 0
        while delivered < max_events:
            try:
                event = self._events.get_nowait()
            except Empty:
                break
            consume(event)
            delivered += 1
        return delivered
