# ds_broadcaster

A Django app for broadcasting Server-Sent Events (SSE) to connected clients via [Datastar](https://data-star.dev). Supports presence tracking, force-disconnect, and channel management.

Requires an ASGI server (e.g. uvicorn). Does not support WSGI.

---

## Installation

Add `ds_broadcaster` to `INSTALLED_APPS` and include its URLs:

```python
# settings.py
INSTALLED_APPS = [
    ...
    "ds_broadcaster",
]

# urls.py
from django.urls import path, include

urlpatterns = [
    ...
    path("events/", include("ds_broadcaster.urls")),
]
```

Import the singleton in any view or module:

```python
from ds_broadcaster import broadcast
```

---

## Core concepts

### Channels

A **channel** is a named pub/sub stream. Any number of clients can connect to a channel and receive events. Channels are created automatically on first connect and destroyed when the last user disconnects.

Channel names are arbitrary strings — `"room-42"`, `"notifications-5"`, `"global"`.

### Users

Each SSE connection is associated with a user ID (the Django `user.pk`). The same user connecting from two tabs counts as two connections but one unique user in presence lists.

---

## API reference

### Sending events

```python
# Send HTML to patch into the DOM (replaces element by id)
broadcast(channel, html)
broadcast.elements(channel, html, selector=None, mode=None)

# Send signals (Datastar reactive state)
broadcast.signals(channel, {"key": "value"})
```

`selector` and `mode` are passed through to Datastar's `datastar-patch-elements` event. `mode` can be `"inner"`, `"outer"`, `"prepend"`, `"append"`, etc.

### Managing channels

```python
# Create a channel explicitly (optional — connect() creates it automatically)
broadcast.new(channel, presence_callback=None)

# Destroy a channel and close all connections
broadcast.kill(channel)

# Inspect the registry
broadcast.get_channels()        # list[str] — active channel names
broadcast.get_users(channel)    # list[int] — connected user IDs (with duplicates for multi-tab)
```

### SSE connections

```python
# Open an SSE stream from a sync view — returns StreamingHttpResponse
broadcast.connect(channel, request, presence_callback=None)

# Force-close all connections for a user (e.g. after removing them from a room)
broadcast.disconnect(channel, user_id)
```

`connect` can be called from a plain sync view — no `async def` required:

```python
@login_required
def room_connect(request, pk):
    room = get_object_or_404(Room, pk=pk, members=request.user)
    return broadcast.connect(f"room-{room.pk}", request, presence_callback=room_presence)
```

On the client, initiate the SSE connection using Datastar's `@get`:

```html
<div data-init="@get('{% url "room_connect" room.pk %}')"></div>
```

---

## Presence callbacks

A **presence callback** generates HTML to broadcast to all clients whenever a user connects or disconnects.

**Signature:** `(channel: str, user_ids: list[int]) -> str`

| Parameter  | Type        | Description                                                    |
|------------|-------------|----------------------------------------------------------------|
| `channel`  | `str`       | The channel name (e.g. `"room-42"`)                           |
| `user_ids` | `list[int]` | Deduplicated IDs of currently connected users                  |

**Rules:**
- Define as a plain sync function — do not use `async def`
- Safe to use Django ORM queries inside it
- Return an HTML string — typically rendered via `render_to_string`
- The HTML should contain an element with a stable `id` so Datastar can patch it in place
- Called automatically on connect and disconnect; no manual invocation needed
- If `None` (default), no presence broadcast is made

**Example — online/offline indicators:**

```python
from django.template.loader import render_to_string
from .models import Room

def room_presence(channel, user_ids):
    room_pk = channel.removeprefix("room-")
    room = Room.objects.get(pk=room_pk)
    online_set = set(user_ids)
    all_members = list(room.members.all())
    online  = [{"user": u, "online": True}  for u in all_members if u.pk in online_set]
    offline = [{"user": u, "online": False} for u in all_members if u.pk not in online_set]
    return render_to_string("rooms/_members.html", {"users": online + offline})

broadcast.connect("room-42", request, presence_callback=room_presence)
```

The presence template must render an element with a stable `id`:

```html
{# rooms/_members.html #}
<div id="room-members" class="flex gap-2">
    {% for item in users %}
    <div class="avatar {% if item.online %}avatar-online{% else %}avatar-offline{% endif %}">
        ...
    </div>
    {% endfor %}
</div>
```

---

## Force-disconnecting a user

Call `broadcast.disconnect(channel, user_id)` to close all SSE connections for a user on a channel. Their stream exits cleanly, the `finally` block fires, and presence is broadcast to remaining clients.

```python
# After removing a user from a room:
room.members.remove(user)
broadcast.disconnect(f"room-{room.pk}", user.pk)
```

---

## Configuration

```python
# settings.py

# Heartbeat interval in seconds (default: 15)
DS_BROADCASTER_HEARTBEAT_INTERVAL = 15
```

---

## Architecture notes

- Each SSE connection gets its own `asyncio.Queue`. Events are pushed into queues from any thread using `call_soon_threadsafe`.
- The registry (`ChannelRegistry`) is a thread-safe in-memory store of channels, queues, and user IDs. It does not persist across server restarts.
- Presence callbacks run in a Django thread pool (via `sync_to_async`) so they never block the async event loop.
- `broadcast.connect` uses `async_to_sync` internally, so callers do not need to be async.
