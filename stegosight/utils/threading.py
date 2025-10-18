"""Threading utilities for running work without blocking the UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


T = TypeVar("T")
E = TypeVar("E", bound=BaseException)


class WorkerSignals(QObject):
    """Signals used by :class:`Worker` for communicating results."""

    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    result = pyqtSignal(object)
    error = pyqtSignal(Exception)
    cancelled = pyqtSignal()


@dataclass
class WorkerConfig(Generic[T]):
    """Configuration used when constructing a :class:`Worker`."""

    fn: Callable[..., T]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None
    cancellable: bool = True


class Worker(QRunnable):
    """QRunnable wrapper that executes *fn* on a thread pool."""

    def __init__(self, config: WorkerConfig[T]) -> None:
        super().__init__()
        self._config = config
        self.signals = WorkerSignals()
        self._is_cancelled = False

    @pyqtSlot()
    def run(self) -> None:
        """Execute the wrapped callable and emit signals."""

        self.signals.started.emit()
        try:
            if self._config.kwargs is None:
                self._config.kwargs = {}
            result = self._config.fn(*self._config.args, **self._config.kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            self.signals.error.emit(exc)
        else:
            if self._is_cancelled:
                self.signals.cancelled.emit()
            else:
                self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

    def cancel(self) -> None:
        """Request cancellation if the worker is cancellable."""

        if self._config.cancellable:
            self._is_cancelled = True
