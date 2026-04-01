from __future__ import annotations

from threading import Lock
from typing import Any, Callable, Dict


class UnifiedAgentController:
    def __init__(self, runner_factory: Callable[[], Callable[..., Dict[str, Any]]] | None = None) -> None:
        self._runner_factory = runner_factory or self._default_runner_factory
        self._runner: Callable[..., Dict[str, Any]] | None = None
        self._lock = Lock()

    def _default_runner_factory(self) -> Callable[..., Dict[str, Any]]:
        from agent import run_agent as runner
        return runner

    def _get_runner(self) -> Callable[..., Dict[str, Any]]:
        if self._runner is None:
            with self._lock:
                if self._runner is None:
                    self._runner = self._runner_factory()
        return self._runner

    def run_agent(self, message: str, user_id: str = "default-user", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        runner = self._get_runner()
        return runner(message, user_id=user_id, meta=meta or {})


_controller: UnifiedAgentController | None = None


def get_agent_controller() -> UnifiedAgentController:
    global _controller
    if _controller is None:
        _controller = UnifiedAgentController()
    return _controller


def run_agent(message: str, user_id: str = "default-user", meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return get_agent_controller().run_agent(message, user_id=user_id, meta=meta)
