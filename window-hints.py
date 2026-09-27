"""Request an undecorated X11 window using correctly typed Motif hints."""

import ctypes
import sys


def undecorate(window_id: int) -> None:
    x11 = ctypes.CDLL("libX11.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("cannot connect to X11/Xwayland")
    try:
        atom = x11.XInternAtom(display, b"_MOTIF_WM_HINTS", 0)
        # Motif hints: decorations flag set, decorations value zero.
        hints = (ctypes.c_ulong * 5)(2, 0, 0, 0, 0)
        x11.XChangeProperty(
            display,
            window_id,
            atom,
            atom,
            32,
            0,
            ctypes.cast(hints, ctypes.c_void_p),
            5,
        )
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)


if __name__ == "__main__":
    try:
        undecorate(int(sys.argv[1], 0))
    except (IndexError, ValueError, OSError, RuntimeError) as exc:
        sys.exit(f"Could not remove window decorations: {exc}")
