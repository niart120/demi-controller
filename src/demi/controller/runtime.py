"""Dedicated worker-thread controller runtime."""

import asyncio
from dataclasses import replace
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING

from demi.application.state import ConnectionState
from demi.controller.adapter import ControllerAdapterError
from demi.controller.commands import (
    ConnectSaved,
    ControllerCommand,
    Disconnect,
    DiscoverAdapters,
    RecreateWithColors,
    RequestStatus,
    Shutdown,
    StartPairing,
)
from demi.controller.events import (
    AdaptersDiscovered,
    ConnectionChanged,
    ControllerError,
    ControllerErrorCategory,
    RuntimeStopped,
    StatusSnapshot,
    WatchdogNeutralized,
)
from demi.controller.mailbox import LatestFrameMailbox
from demi.controller.watchdog import FrameWatchdog, WatchdogClock
from demi.domain.controller import AccelG, ControllerFrame, GyroRate, StickVector

if TYPE_CHECKING:
    from demi.controller.adapter import (
        ControllerAdapter,
        ControllerAdapterFactory,
        RuntimeEventSink,
    )


class ControllerRuntime:
    """Own the adapter on a dedicated asyncio worker thread."""

    def __init__(
        self,
        *,
        adapter_factory: "ControllerAdapterFactory",
        event_sink: "RuntimeEventSink",
        clock: WatchdogClock,
    ) -> None:
        """Initialize a stopped runtime with injected adapter and clock."""
        self._adapter_factory = adapter_factory
        self._event_sink = event_sink
        self._clock = clock
        self._mailbox = LatestFrameMailbox()
        self._watchdog = FrameWatchdog(clock=clock)
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._commands: asyncio.Queue[ControllerCommand] | None = None
        self._frame_event: asyncio.Event | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._state_lock = Lock()
        self._shutdown_requested = False
        self._ready = Event()
        self._adapter: ControllerAdapter | None = None
        self._connection_state = ConnectionState.STOPPED
        self._latest_frame: ControllerFrame | None = None
        self._connected = False
        self._connected_adapter_id: str | None = None
        self._runtime_stopped = False
        self._diagnostic_counter = 0

    @property
    def is_alive(self) -> bool:
        """Return whether the dedicated worker thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def connection_state(self) -> ConnectionState:
        """Return the latest worker connection state."""
        return self._connection_state

    @property
    def latest_frame(self) -> ControllerFrame | None:
        """Return the latest accepted frame, including when disconnected."""
        return self._latest_frame

    @property
    def watchdog_tripped(self) -> bool:
        """Return whether the current capture epoch tripped the watchdog."""
        return self._watchdog.watchdog_tripped

    def start(self) -> None:
        """Start the non-daemon worker thread and its asyncio event loop.

        Raises:
            RuntimeError: The worker does not become ready within five seconds.
        """
        with self._state_lock:
            if self.is_alive:
                return
            self._ready.clear()
            self._runtime_stopped = False
            self._shutdown_requested = False
            self._thread = Thread(target=self._thread_main, name="demi-controller")
            self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError

    def post(self, command: ControllerCommand) -> None:
        """Queue an ordered command for the worker thread.

        Args:
            command: Immutable command to execute after earlier commands.

        Raises:
            RuntimeError: The runtime is stopped or shutdown has started.
        """
        with self._state_lock:
            loop = self._loop
            commands = self._commands
            if self._shutdown_requested or loop is None or commands is None or not self.is_alive:
                raise RuntimeError
            loop.call_soon_threadsafe(commands.put_nowait, command)

    def offer_frame(self, frame: ControllerFrame) -> bool:
        """Offer a frame to the latest-value slot.

        Returns:
            ``True`` when the frame replaced the mailbox value. ``False`` when
            it is stale or shutdown has started.
        """
        with self._state_lock:
            if self._shutdown_requested:
                return False
            accepted = self._mailbox.offer(frame)
            if not accepted:
                return False
            self._latest_frame = frame
            loop = self._loop
            frame_event = self._frame_event
            if loop is not None and frame_event is not None and self.is_alive:
                loop.call_soon_threadsafe(frame_event.set)
            return True

    def close(self) -> None:
        """Cancel active adapter work, run cleanup, and join the worker.

        Concurrent and repeated calls wait for or observe the same shutdown.

        Raises:
            RuntimeError: The worker does not stop within five seconds.
        """
        with self._state_lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                return
            if not self._shutdown_requested:
                self._shutdown_requested = True
                loop = self._loop
                shutdown_event = self._shutdown_event
                if loop is not None and shutdown_event is not None:
                    loop.call_soon_threadsafe(shutdown_event.set)
        thread.join(timeout=5.0)
        if thread.is_alive():
            raise RuntimeError

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._commands = asyncio.Queue()
        self._frame_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._ready.set()
        try:
            loop.run_until_complete(self._worker_main())
        finally:
            self._loop = None
            self._commands = None
            self._frame_event = None
            self._shutdown_event = None
            loop.close()

    async def _worker_main(self) -> None:
        command_task: asyncio.Task[ControllerCommand] | None = None
        frame_task: asyncio.Task[bool] | None = None
        watchdog_task: asyncio.Task[None] | None = None
        shutdown_task: asyncio.Task[bool] | None = None
        commands = self._commands
        frame_event = self._frame_event
        shutdown_event = self._shutdown_event
        if commands is None or frame_event is None or shutdown_event is None:
            return
        try:
            self._adapter = self._adapter_factory()
            self._set_connection_state(ConnectionState.READY)
            if self._mailbox.peek() is not None:
                frame_event.set()
            command_task = asyncio.create_task(commands.get())
            frame_task = asyncio.create_task(frame_event.wait())
            watchdog_task = asyncio.create_task(self._watchdog_loop())
            shutdown_task = asyncio.create_task(shutdown_event.wait())
            while True:
                done, _ = await asyncio.wait(
                    {command_task, frame_task, watchdog_task, shutdown_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if shutdown_task in done:
                    break
                if command_task in done:
                    command = command_task.result()
                    if isinstance(command, Shutdown):
                        with self._state_lock:
                            self._shutdown_requested = True
                        break
                    operation_task = asyncio.create_task(self._handle_command(command))
                    if not await self._complete_operation_or_shutdown(
                        operation_task, shutdown_task
                    ):
                        break
                    command_task = asyncio.create_task(commands.get())
                if frame_task in done:
                    frame_event.clear()
                    operation_task = asyncio.create_task(self._consume_latest_frame())
                    if not await self._complete_operation_or_shutdown(
                        operation_task, shutdown_task
                    ):
                        break
                    frame_task = asyncio.create_task(frame_event.wait())
                if watchdog_task in done:
                    watchdog_task.result()
                    await self._neutralize_for_watchdog()
                    watchdog_task = asyncio.create_task(self._watchdog_loop())
        except Exception as error:  # noqa: BLE001
            self._emit_error(
                self._category_for_error(error, ControllerErrorCategory.UNEXPECTED), error
            )
        finally:
            pending_tasks = tuple(
                task
                for task in (command_task, frame_task, watchdog_task, shutdown_task)
                if task is not None
            )
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
            await self._shutdown_adapter()

    @staticmethod
    async def _complete_operation_or_shutdown(
        operation_task: asyncio.Task[None],
        shutdown_task: asyncio.Task[bool],
    ) -> bool:
        """Complete one adapter operation or cancel it for shutdown."""
        done, _ = await asyncio.wait(
            {operation_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if shutdown_task in done:
            operation_task.cancel()
            await asyncio.gather(operation_task, return_exceptions=True)
            return False
        operation_task.result()
        return True

    async def _watchdog_loop(self) -> None:
        while True:
            await asyncio.sleep(FrameWatchdog.monitor_interval_ms / 1000.0)
            if self._watchdog.check():
                return

    async def _handle_command(self, command: ControllerCommand) -> None:
        if isinstance(command, DiscoverAdapters):
            await self._discover_adapters()
        elif isinstance(command, ConnectSaved):
            await self._connect_saved(command)
        elif isinstance(command, StartPairing):
            await self._start_pairing(command)
        elif isinstance(command, Disconnect):
            await self._disconnect()
        elif isinstance(command, RecreateWithColors):
            await self._recreate_colors(command)
        elif isinstance(command, RequestStatus):
            self._emit_status()

    async def _discover_adapters(self) -> None:
        adapter = self._acquire_adapter()
        if adapter is None:
            return
        adapter_id = self._connected_adapter_id if self._connected else None
        self._set_connection_state(ConnectionState.DISCOVERING, adapter_id)
        try:
            descriptors = await adapter.discover_adapters()
            self._event_sink.emit(AdaptersDiscovered(adapters=descriptors))
        except Exception as error:  # noqa: BLE001
            self._emit_error(
                self._category_for_error(error, ControllerErrorCategory.ADAPTER_OPEN_FAILED),
                error,
            )
        finally:
            if self._connected:
                self._set_connection_state(
                    ConnectionState.CONNECTED,
                    self._connected_adapter_id,
                )
            else:
                self._set_connection_state(ConnectionState.READY)

    async def _connect_saved(self, command: ConnectSaved) -> None:
        adapter = self._acquire_adapter()
        if adapter is None:
            return
        self._set_connection_state(ConnectionState.CONNECTING, command.adapter_id)
        try:
            await adapter.connect_saved(
                command.adapter_id,
                command.bond_path,
                command.timeout_seconds,
                command.colors,
            )
            self._connected = True
            self._connected_adapter_id = command.adapter_id
            self._watchdog.set_connected(True)
            await self._apply_connection_initial_state()
            self._set_connection_state(ConnectionState.CONNECTED, command.adapter_id)
        except Exception as error:  # noqa: BLE001
            self._connected = False
            self._connected_adapter_id = None
            self._watchdog.set_connected(False)
            await self._emit_error_and_recover(
                error,
                ControllerErrorCategory.RECONNECT_FAILED,
            )

    async def _start_pairing(self, command: StartPairing) -> None:
        adapter = self._acquire_adapter()
        if adapter is None:
            return
        self._set_connection_state(ConnectionState.CONNECTING, command.adapter_id)
        try:
            await adapter.start_pairing(
                command.adapter_id,
                command.bond_path,
                command.timeout_seconds,
                command.colors,
            )
            self._connected = True
            self._connected_adapter_id = command.adapter_id
            self._watchdog.set_connected(True)
            await self._apply_connection_initial_state()
            self._set_connection_state(ConnectionState.CONNECTED, command.adapter_id)
        except Exception as error:  # noqa: BLE001
            self._connected = False
            self._connected_adapter_id = None
            self._watchdog.set_connected(False)
            await self._emit_error_and_recover(
                error,
                ControllerErrorCategory.PAIRING_TIMEOUT,
            )

    async def _disconnect(self) -> None:
        adapter = self._adapter
        if adapter is None:
            return
        self._set_connection_state(ConnectionState.DISCONNECTING)
        try:
            if self._connected:
                self._mailbox.discard_pending(reason="disconnect")
                await self._disconnect_after_rest(adapter)
        except Exception as error:  # noqa: BLE001
            self._emit_error(
                self._category_for_error(error, ControllerErrorCategory.SHUTDOWN_FAILED),
                error,
            )
        finally:
            self._connected = False
            self._connected_adapter_id = None
            self._watchdog.set_connected(False)
            self._set_connection_state(ConnectionState.READY)

    async def _recreate_colors(self, command: RecreateWithColors) -> None:
        adapter = self._adapter
        if adapter is None or not self._connected:
            return
        adapter_id = self._connected_adapter_id
        self._connected = False
        self._watchdog.set_connected(False)
        self._set_connection_state(ConnectionState.CONNECTING, adapter_id)
        try:
            self._mailbox.discard_pending(reason="color_recreate")
            await self._apply_rest_state()
            await adapter.recreate_with_colors(command.colors, neutral=False)
            self._connected = True
            self._watchdog.set_connected(True)
            await self._apply_connection_initial_state()
            self._set_connection_state(ConnectionState.CONNECTED, adapter_id)
        except Exception as error:  # noqa: BLE001
            self._mailbox.discard_pending(reason="send_failure")
            self._connected = False
            self._connected_adapter_id = None
            self._watchdog.set_connected(False)
            await self._emit_error_and_recover(
                error,
                ControllerErrorCategory.CONNECTION_LOST,
            )

    async def _consume_latest_frame(self) -> None:
        frame = self._mailbox.take()
        if frame is None:
            return
        self._watchdog.note_frame(frame)
        if not self._connected or self._adapter is None:
            return
        if frame.capture_active and self._watchdog.watchdog_tripped:
            return
        try:
            await self._adapter.send_frame(frame)
        except Exception as error:  # noqa: BLE001
            self._connected = False
            self._watchdog.set_connected(False)
            await self._emit_error_and_recover(
                error,
                ControllerErrorCategory.CONNECTION_LOST,
            )

    async def _neutralize_for_watchdog(self) -> None:
        if not self._connected or self._adapter is None:
            return
        try:
            await self._apply_rest_state()
            self._event_sink.emit(
                WatchdogNeutralized(capture_epoch=self._watchdog.capture_epoch or 0)
            )
        except Exception as error:  # noqa: BLE001
            self._connected = False
            self._watchdog.set_connected(False)
            await self._emit_error_and_recover(
                error,
                ControllerErrorCategory.CONNECTION_LOST,
            )

    async def _apply_rest_state(self) -> None:
        if self._adapter is not None:
            await self._adapter.send_frame(self._neutral_frame())

    async def _apply_connection_initial_state(self) -> None:
        if self._adapter is not None:
            await self._adapter.send_frame(self._connection_initial_frame())

    async def _disconnect_after_rest(self, adapter: "ControllerAdapter") -> None:
        """Send Project_Demi rest before closing without a duplicate neutral."""
        rest_sent = False
        try:
            self._mailbox.discard_pending(reason="watchdog")
            await self._apply_rest_state()
            rest_sent = True
        finally:
            await adapter.disconnect(neutral=not rest_sent)

    def _connection_initial_frame(self) -> ControllerFrame:
        frame = self._neutral_frame()
        latest = self._latest_frame
        if latest is not None and latest.capture_active and latest.accel_g == AccelG(0.0, 0.0, 0.0):
            return replace(frame, accel_g=latest.accel_g)
        return frame

    def _neutral_frame(self) -> ControllerFrame:
        return ControllerFrame(
            sequence=max(self._mailbox.last_sequence + 1, 0),
            capture_epoch=self._mailbox.current_epoch or 0,
            monotonic_ns=self._clock.monotonic_ns(),
            buttons=frozenset(),
            left_stick=StickVector(x=0.0, y=0.0),
            right_stick=StickVector(x=0.0, y=0.0),
            gyro_rate=GyroRate(0.0, 0.0, 0.0),
            accel_g=AccelG(0.0, 0.0, 1.0),
            capture_active=False,
        )

    async def _shutdown_adapter(self) -> None:
        if self._runtime_stopped:
            return
        adapter = self._adapter
        try:
            if adapter is not None:
                if self._connected:
                    try:
                        self._mailbox.discard_pending(reason="shutdown")
                        await self._disconnect_after_rest(adapter)
                    except Exception as error:  # noqa: BLE001
                        self._emit_error(
                            self._category_for_error(
                                error, ControllerErrorCategory.SHUTDOWN_FAILED
                            ),
                            error,
                        )
                await adapter.close()
        except Exception as error:  # noqa: BLE001
            self._emit_error(
                self._category_for_error(error, ControllerErrorCategory.SHUTDOWN_FAILED),
                error,
            )
        finally:
            self._connected = False
            self._connected_adapter_id = None
            self._watchdog.set_connected(False)
            self._adapter = None
            self._set_connection_state(ConnectionState.STOPPED)
            self._event_sink.emit(RuntimeStopped())
            self._runtime_stopped = True

    async def _emit_error_and_recover(
        self,
        error: Exception,
        fallback: ControllerErrorCategory,
    ) -> None:
        """Release a failed connection and return the runtime to ready."""
        self._connected = False
        self._connected_adapter_id = None
        self._watchdog.set_connected(False)
        self._set_connection_state(ConnectionState.ERROR)
        self._emit_error(self._category_for_error(error, fallback), error)
        await self._best_effort_release_adapter()
        self._set_connection_state(ConnectionState.READY)

    async def _best_effort_release_adapter(self) -> None:
        """Disconnect and close an adapter while preserving later cleanup."""
        adapter = self._adapter
        self._adapter = None
        if adapter is None:
            return
        self._mailbox.discard_pending(reason="recovery")
        try:
            await adapter.disconnect(neutral=True)
        except Exception as error:  # noqa: BLE001
            self._emit_error(
                self._category_for_error(error, ControllerErrorCategory.SHUTDOWN_FAILED),
                error,
            )
        try:
            await adapter.close()
        except Exception as error:  # noqa: BLE001
            self._emit_error(
                self._category_for_error(error, ControllerErrorCategory.SHUTDOWN_FAILED),
                error,
            )

    def _acquire_adapter(self) -> "ControllerAdapter | None":
        """Return a live adapter, recreating one that recovery released."""
        adapter = self._adapter
        if adapter is not None:
            return adapter
        try:
            adapter = self._adapter_factory()
        except Exception as error:  # noqa: BLE001
            self._set_connection_state(ConnectionState.ERROR)
            self._emit_error(
                self._category_for_error(
                    error,
                    ControllerErrorCategory.ADAPTER_OPEN_FAILED,
                ),
                error,
            )
            self._set_connection_state(ConnectionState.READY)
            return None
        self._adapter = adapter
        return adapter

    def _set_connection_state(
        self,
        state: ConnectionState,
        adapter_id: str | None = None,
        summary: str = "",
    ) -> None:
        self._connection_state = state
        self._event_sink.emit(
            ConnectionChanged(state=state, adapter_id=adapter_id, summary=summary)
        )

    def _emit_status(self) -> None:
        self._event_sink.emit(
            StatusSnapshot(
                connection_state=self._connection_state,
                latest_frame=self._latest_frame,
                watchdog_tripped=self._watchdog.watchdog_tripped,
            )
        )

    @staticmethod
    def _category_for_error(
        error: Exception,
        fallback: ControllerErrorCategory,
    ) -> ControllerErrorCategory:
        if isinstance(error, ControllerAdapterError):
            return error.category
        return fallback

    def _emit_error(self, category: ControllerErrorCategory, error: Exception) -> None:
        self._diagnostic_counter += 1
        self._event_sink.emit(
            ControllerError(
                category=category,
                summary=category.value,
                retryable=category
                in {
                    ControllerErrorCategory.ADAPTER_OPEN_FAILED,
                    ControllerErrorCategory.RECONNECT_FAILED,
                    ControllerErrorCategory.CONNECTION_LOST,
                },
                diagnostic_id=f"runtime-{self._diagnostic_counter:04d}",
            )
        )
        del error
