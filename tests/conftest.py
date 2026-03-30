from __future__ import annotations

import io
import sys
import types
from contextlib import contextmanager


def _install_colorama_stub() -> None:
    if "colorama" in sys.modules:
        return

    colorama = types.ModuleType("colorama")
    colorama.Fore = types.SimpleNamespace(GREEN="", RED="")
    colorama.Style = types.SimpleNamespace(DIM="", RESET_ALL="")
    sys.modules["colorama"] = colorama


def _install_rich_stub() -> None:
    if "rich" in sys.modules:
        return

    rich = types.ModuleType("rich")
    console_mod = types.ModuleType("rich.console")
    panel_mod = types.ModuleType("rich.panel")
    style_mod = types.ModuleType("rich.style")
    text_mod = types.ModuleType("rich.text")

    class Text:
        def __init__(self, text: str = "", style: str | None = None) -> None:
            del style
            self._parts: list[str] = []
            if text:
                self._parts.append(str(text))

        def append(self, text: str, style: str | None = None) -> None:
            del style
            self._parts.append(str(text))

        def __str__(self) -> str:
            return "".join(self._parts)

    class Panel:
        def __init__(
            self,
            renderable: object,
            *args: object,
            **kwargs: object,
        ) -> None:
            del args, kwargs
            self.renderable = renderable

        def __str__(self) -> str:
            return str(self.renderable)

    class Style:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

    class _Capture:
        def __init__(self, console: "Console") -> None:
            self._console = console
            self._buffer = io.StringIO()
            self._previous: io.StringIO | None = None

        def __enter__(self) -> "_Capture":
            self._previous = self._console._capture_buffer
            self._console._capture_buffer = self._buffer
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb
            self._console._capture_buffer = self._previous

        def get(self) -> str:
            return self._buffer.getvalue()

    class Console:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            self._capture_buffer: io.StringIO | None = None

        @contextmanager
        def capture(self):
            capture = _Capture(self)
            try:
                yield capture.__enter__()
            finally:
                capture.__exit__(None, None, None)

        def print(self, *objects: object, end: str = "\n", **kwargs: object) -> None:
            del kwargs
            text = "".join(str(obj) for obj in objects) + end
            if self._capture_buffer is not None:
                self._capture_buffer.write(text)

    console_mod.Console = Console
    panel_mod.Panel = Panel
    style_mod.Style = Style
    text_mod.Text = Text

    rich.console = console_mod
    rich.panel = panel_mod
    rich.style = style_mod
    rich.text = text_mod

    sys.modules["rich"] = rich
    sys.modules["rich.console"] = console_mod
    sys.modules["rich.panel"] = panel_mod
    sys.modules["rich.style"] = style_mod
    sys.modules["rich.text"] = text_mod


def _install_pynput_stub() -> None:
    if "pynput" in sys.modules:
        return

    pynput = types.ModuleType("pynput")
    keyboard_mod = types.ModuleType("pynput.keyboard")

    class Key:
        esc = "esc"

    class Listener:
        def __init__(self, on_press=None, *args: object, **kwargs: object) -> None:
            del args, kwargs
            self.on_press = on_press

        def start(self) -> "Listener":
            return self

        def stop(self) -> None:
            return None

    keyboard_mod.Key = Key
    keyboard_mod.Listener = Listener
    pynput.keyboard = keyboard_mod

    sys.modules["pynput"] = pynput
    sys.modules["pynput.keyboard"] = keyboard_mod


_install_colorama_stub()
_install_rich_stub()
_install_pynput_stub()
