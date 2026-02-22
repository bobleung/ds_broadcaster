import time

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import StreamingHttpResponse
from django.shortcuts import render

from . import broadcast
from .formatting import format_patch_elements


# --- Test views ---


@staff_member_required
def test_page(request):
    """Test page for ds_broadcaster."""
    return render(request, "ds_broadcaster/test.html")


@staff_member_required
def test_sse(request, channel):
    """Test SSE endpoint — staff only."""
    return broadcast.connect(channel, request)


def _get_channel(request):
    """Read channel_name from Datastar signals (POST body or GET param)."""
    if request.method == "POST" and request.body:
        try:
            signals = json.loads(request.body)
            return signals.get("channel_name", "test-channel")
        except (json.JSONDecodeError, AttributeError):
            pass
    return request.GET.get("channel_name", "").strip("'\"") or "test-channel"


def _log_entry(message):
    """Format a timestamped log entry as HTML."""
    ts = time.strftime("%H:%M:%S")
    return (
        f'<div><span class="text-gray-500">[{ts}]</span> {message}</div>'
    )


def _sse_response(*fragments):
    """Return a StreamingHttpResponse with pre-formatted SSE events."""
    async def stream():
        for f in fragments:
            yield f
    return StreamingHttpResponse(stream(), content_type="text/event-stream")



@staff_member_required
def test_new(request):
    """Test broadcast.new — create a channel."""
    channel = _get_channel(request)
    broadcast.new(channel)
    return _sse_response(
        format_patch_elements(
            _log_entry(f'broadcast.new("<b>{channel}</b>") — channel created'),
            selector="#event_log",
            mode="prepend",
        ),
        _registry_status_fragment(),
    )



@staff_member_required
def test_kill(request):
    """Test broadcast.kill — destroy a channel."""
    channel = _get_channel(request)
    broadcast.kill(channel)
    return _sse_response(
        format_patch_elements(
            _log_entry(f'broadcast.kill("<b>{channel}</b>") — channel destroyed'),
            selector="#event_log",
            mode="prepend",
        ),
        _registry_status_fragment(),
    )



@staff_member_required
def test_send_elements(request):
    """Test broadcast() — send elements to a channel."""
    channel = _get_channel(request)
    ts = time.strftime("%H:%M:%S")
    broadcast(
        channel,
        f'<div class="alert alert-success alert-sm">'
        f'<span>Element broadcast at {ts}</span></div>',
        selector="#broadcast_target",
        mode="append",
    )
    return _sse_response(
        format_patch_elements(
            _log_entry(f'broadcast("<b>{channel}</b>", html) — element sent'),
            selector="#event_log",
            mode="prepend",
        ),
    )



@staff_member_required
def test_send_signals(request):
    """Test broadcast.signals — send signals to a channel."""
    channel = _get_channel(request)
    ts = time.strftime("%H:%M:%S")
    broadcast.signals(channel, {
        "last_signal_time": ts,
        "signal_count": 1,
        "message": f"Signal sent at {ts}",
    })
    return _sse_response(
        format_patch_elements(
            _log_entry(f'broadcast.signals("<b>{channel}</b>", dict) — signals sent'),
            selector="#event_log",
            mode="prepend",
        ),
    )


@staff_member_required
def test_status(request):
    """Return current registry status."""
    return _sse_response(
        _registry_status_fragment(),
        format_patch_elements(
            _log_entry("Registry status refreshed"),
            selector="#event_log",
            mode="prepend",
        ),
    )


def _registry_status_fragment():
    """Build an SSE fragment showing the current registry state."""
    channel_names = broadcast.get_channels()

    channel_info = {}
    for ch in channel_names:
        user_ids = broadcast.get_users(ch)
        unique_ids = sorted(set(user_ids))
        channel_info[ch] = {"count": len(user_ids), "ids": unique_ids}

    if not channel_info:
        content = '<p class="text-gray-400">No channels</p>'
    else:
        rows = "".join(
            f"<tr><td>{ch}</td><td>{info['count']}</td>"
            f"<td>{', '.join(str(i) for i in info['ids']) or '—'}</td></tr>"
            for ch, info in sorted(channel_info.items())
        )
        content = (
            '<table class="table table-sm">'
            "<thead><tr><th>Channel</th><th>Connections</th><th>User IDs</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    return format_patch_elements(
        content,
        selector="#registry_status",
        mode="inner",
    )
