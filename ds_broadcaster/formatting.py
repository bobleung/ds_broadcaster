import json


def format_patch_elements(html, *, selector=None, mode=None):
    """Format a datastar-patch-elements SSE event."""
    lines = ["event: datastar-patch-elements"]
    if mode is not None:
        lines.append(f"data: mode {mode}")
    if selector is not None:
        lines.append(f"data: selector {selector}")
    lines.append(f"data: elements {' '.join(html.split())}")
    return "\n".join(lines) + "\n\n"


def format_patch_signals(signals):
    """Format a datastar-patch-signals SSE event."""
    signals_json = json.dumps(signals, separators=(",", ":"))
    return f"event: datastar-patch-signals\ndata: signals {signals_json}\n\n"


HEARTBEAT = ": ping\n\n"
