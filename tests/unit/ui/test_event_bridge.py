from threading import Thread

from demi.ui.event_bridge import MainThreadEventBridge


def test_worker_event_is_delivered_only_when_the_main_thread_drains() -> None:
    received: list[str] = []
    bridge: MainThreadEventBridge[str] = MainThreadEventBridge()

    worker = Thread(target=lambda: bridge.emit("connected"))
    worker.start()
    worker.join()

    assert received == []
    assert bridge.drain(received.append) == 1
    assert received == ["connected"]


def test_event_bridge_preserves_fifo_order_and_honors_a_drain_limit() -> None:
    received: list[int] = []
    bridge: MainThreadEventBridge[int] = MainThreadEventBridge()
    for event in (1, 2, 3):
        bridge.emit(event)

    assert bridge.drain(received.append, max_events=2) == 2
    assert received == [1, 2]
    assert bridge.drain(received.append) == 1
    assert received == [1, 2, 3]
