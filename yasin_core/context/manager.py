import contextlib
from contextvars import ContextVar
from typing import Any, Dict


class Context:


    def __init__(self, data: Dict[str, Any] = None):

        self._data = dict(data) if data is not None else {}


    def get(self, key: str, default: Any = None) -> Any:

        return self._data.get(key, default)


    def set(self, key: str, value: Any) -> None:

        self._data[key] = value


    def delete(self, key: str) -> None:

        if key in self._data:

            del self._data[key]


    def clear(self) -> None:

        self._data.clear()


    def to_dict(self) -> Dict[str, Any]:

        return dict(self._data)


_current_context: ContextVar[Context] = ContextVar("current_context", default=None)


def get_current_context() -> Context:

    ctx = _current_context.get()

    if ctx is None:

        ctx = Context()

        _current_context.set(ctx)

    return ctx


@contextlib.contextmanager
def active_context(context: Context):

    token = _current_context.set(context)

    try:

        yield context

    finally:

        _current_context.reset(token)
