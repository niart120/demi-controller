"""Main-thread presentation state derived from application events."""

from dataclasses import dataclass

from .state import ConnectionState


@dataclass(frozen=True, slots=True)
class AdapterOption:
    """Safe adapter identity and user-facing label."""

    id: str
    label: str


@dataclass(frozen=True, slots=True)
class ApplicationPresentation:
    """Immutable values consumed by the desktop UI."""

    connection_state: ConnectionState
    adapter_id: str | None
    adapter_label: str
    adapters: tuple[AdapterOption, ...]
    warning: str
    error: str | None
    recovery_notice: str | None
    color_reconnect_pending: bool


class PresentationStore:
    """Own mutable main-thread presentation state for one application session."""

    def __init__(self) -> None:
        """Initialize the disconnected presentation without warnings."""
        self._model = ApplicationPresentation(
            connection_state=ConnectionState.STOPPED,
            adapter_id=None,
            adapter_label="なし",
            adapters=(),
            warning="",
            error=None,
            recovery_notice=None,
            color_reconnect_pending=False,
        )

    @property
    def model(self) -> ApplicationPresentation:
        """Return the latest UI presentation snapshot."""
        return self._model

    def set_connection(
        self,
        state: ConnectionState,
        *,
        adapter_id: str | None = None,
        adapter_label: str | None = None,
    ) -> None:
        """Update connection presentation and clear errors on success.

        Args:
            state: Runtime connection state reported to the main thread.
            adapter_id: Selected adapter identity when the runtime reports one.
            adapter_label: Safe display label for the selected adapter.
        """
        succeeded = state is ConnectionState.CONNECTED
        self._model = ApplicationPresentation(
            connection_state=state,
            adapter_id=adapter_id if adapter_id is not None else self._model.adapter_id,
            adapter_label=(
                adapter_label if adapter_label is not None else self._model.adapter_label
            ),
            adapters=self._model.adapters,
            warning="" if succeeded else self._model.warning,
            error=None if succeeded else self._model.error,
            recovery_notice=self._model.recovery_notice,
            color_reconnect_pending=self._model.color_reconnect_pending,
        )

    def set_adapters(self, adapters: tuple[AdapterOption, ...]) -> None:
        """Replace the current discovery result.

        Args:
            adapters: Candidate adapters available for explicit selection.
        """
        adapter_label = self._model.adapter_label
        if self._model.adapter_id is not None:
            for adapter in adapters:
                if adapter.id == self._model.adapter_id:
                    adapter_label = adapter.label
                    break
        self._model = ApplicationPresentation(
            connection_state=self._model.connection_state,
            adapter_id=self._model.adapter_id,
            adapter_label=adapter_label,
            adapters=adapters,
            warning=self._model.warning,
            error=self._model.error,
            recovery_notice=self._model.recovery_notice,
            color_reconnect_pending=self._model.color_reconnect_pending,
        )

    def has_adapter(self, adapter_id: str) -> bool:
        """Return whether discovery contains the exact adapter identity."""
        return any(adapter.id == adapter_id for adapter in self._model.adapters)

    def set_error(self, message: str) -> None:
        """Keep a safe error message until success or explicit acknowledgement."""
        self._model = ApplicationPresentation(
            connection_state=self._model.connection_state,
            adapter_id=self._model.adapter_id,
            adapter_label=self._model.adapter_label,
            adapters=self._model.adapters,
            warning=message,
            error=message,
            recovery_notice=self._model.recovery_notice,
            color_reconnect_pending=self._model.color_reconnect_pending,
        )

    def acknowledge_error(self) -> None:
        """Clear a user-visible error after an explicit retry or acknowledgement."""
        self._model = ApplicationPresentation(
            connection_state=self._model.connection_state,
            adapter_id=self._model.adapter_id,
            adapter_label=self._model.adapter_label,
            adapters=self._model.adapters,
            warning="",
            error=None,
            recovery_notice=self._model.recovery_notice,
            color_reconnect_pending=self._model.color_reconnect_pending,
        )

    def set_warning(self, message: str) -> None:
        """Show a safe transient warning without replacing an error."""
        self._model = ApplicationPresentation(
            connection_state=self._model.connection_state,
            adapter_id=self._model.adapter_id,
            adapter_label=self._model.adapter_label,
            adapters=self._model.adapters,
            warning=self._model.error or message,
            error=self._model.error,
            recovery_notice=self._model.recovery_notice,
            color_reconnect_pending=self._model.color_reconnect_pending,
        )

    def set_recovery_notice(self, notice: str | None) -> None:
        """Set the one-time safe settings recovery notice."""
        self._model = ApplicationPresentation(
            connection_state=self._model.connection_state,
            adapter_id=self._model.adapter_id,
            adapter_label=self._model.adapter_label,
            adapters=self._model.adapters,
            warning=self._model.warning,
            error=self._model.error,
            recovery_notice=notice,
            color_reconnect_pending=self._model.color_reconnect_pending,
        )

    def acknowledge_recovery_notice(self, expected_notice: str) -> bool:
        """Clear a recovery notice only after the matching text was rendered."""
        if self._model.recovery_notice != expected_notice:
            return False
        self.set_recovery_notice(None)
        return True

    def set_color_reconnect_pending(self, pending: bool) -> None:
        """Update whether the UI must offer an explicit color reconnect choice."""
        self._model = ApplicationPresentation(
            connection_state=self._model.connection_state,
            adapter_id=self._model.adapter_id,
            adapter_label=self._model.adapter_label,
            adapters=self._model.adapters,
            warning=self._model.warning,
            error=self._model.error,
            recovery_notice=self._model.recovery_notice,
            color_reconnect_pending=pending,
        )
