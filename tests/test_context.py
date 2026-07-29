import threading
from yasin_core.context import Context, get_current_context, active_context


def test_context_basic():

    ctx = Context({"a": 1})

    assert ctx.get("a") == 1

    assert ctx.get("b") is None

    assert ctx.get("b", 2) == 2


    ctx.set("b", 3)

    assert ctx.get("b") == 3


    assert ctx.to_dict() == {"a": 1, "b": 3}


    ctx.delete("a")

    assert ctx.get("a") is None


    ctx.clear()

    assert ctx.to_dict() == {}


def test_current_context():

    ctx1 = get_current_context()

    ctx1.set("foo", "bar")


    ctx2 = get_current_context()

    assert ctx2.get("foo") == "bar"


def test_active_context_manager():

    ctx1 = get_current_context()

    ctx1.set("val", "outer")


    new_ctx = Context({"val": "inner"})


    with active_context(new_ctx):

        assert get_current_context().get("val") == "inner"


    assert get_current_context().get("val") == "outer"


def test_context_thread_isolation():

    ctx = get_current_context()

    ctx.set("shared", "main_thread")


    result = {}


    def thread_func():

        # In a new thread, contextvars should default to clean or isolated values
        t_ctx = get_current_context()

        result["initial"] = t_ctx.get("shared")

        t_ctx.set("shared", "child_thread")

        result["mutated"] = t_ctx.get("shared")


    thread = threading.Thread(target=thread_func)

    thread.start()

    thread.join()


    # The child thread shouldn't see main thread's value initially because they are isolated
    assert result["initial"] is None

    assert result["mutated"] == "child_thread"

    # Main thread's value should remain unchanged
    assert get_current_context().get("shared") == "main_thread"
