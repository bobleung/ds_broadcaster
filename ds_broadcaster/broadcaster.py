import asyncio

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import StreamingHttpResponse

from .formatting import HEARTBEAT, format_patch_elements, format_patch_signals
from .registry import registry

HEARTBEAT_INTERVAL = getattr(settings, "DS_BROADCASTER_HEARTBEAT_INTERVAL", 15)

_CLOSE = object()  # sentinel pushed into a queue to force-close that stream


class Broadcaster:
    """
    Callable namespace for SSE broadcasting over Datastar.

    Usage:
        broadcast(channel, html)                          # send elements (default)
        broadcast.elements(channel, html, ...)            # send elements (explicit)
        broadcast.signals(channel, signals_dict)          # send signals
        broadcast.new(channel, presence_callback=fn)      # create channel (optional presence)
        broadcast.connect(channel, request)               # open SSE stream + register user + broadcast presence
        broadcast.disconnect(channel, user_id)            # force-close a user's connections + broadcast presence
        broadcast.kill(channel)                           # destroy channel (closes all connections)
        broadcast.get_users(channel)                      # get list of connected user IDs (int)
        broadcast.get_channels()                          # list active channels

    Presence callbacks
    ------------------
    A presence callback is an optional callable that generates HTML to broadcast
    to all clients on a channel whenever a user connects or disconnects.

    Signature: (channel: str, user_ids: list[int]) -> str

        channel   — the channel name (e.g. "room-42")
        user_ids  — deduplicated list of IDs of users currently connected
                    (same user on multiple tabs counts once)

    The callback is called synchronously in a thread pool — it is safe to use
    Django ORM queries inside it. Do not define it as async.

    The returned HTML string is broadcast to all connected clients as a
    datastar-patch-elements event (replacing the element with id="room-members"
    by default, or whatever id your presence template renders).

    Example — presence with online/offline indicators:

        def room_presence(channel, user_ids):
            room_pk = channel.removeprefix("room-")
            room = Room.objects.get(pk=room_pk)
            online_set = set(user_ids)
            all_members = room.members.all()
            users = [
                {"user": u, "online": u.pk in online_set}
                for u in all_members
            ]
            users.sort(key=lambda x: not x["online"])  # online first
            return render_to_string("rooms/_members.html", {"users": users})

        broadcast.connect("room-42", request, presence_callback=room_presence)

    If presence_callback is None (the default), no presence broadcast is made
    on connect or disconnect.
    """

    def __call__(self, channel, html, *, selector=None, mode=None):
        """Send elements (default). Alias for self.elements()."""
        self.elements(channel, html, selector=selector, mode=mode)

    def elements(self, channel, html, *, selector=None, mode=None):
        """Send a datastar-patch-elements event to all clients on the channel."""
        event = format_patch_elements(html, selector=selector, mode=mode)
        self._put(channel, event)

    def signals(self, channel, signals):
        """Send a datastar-patch-signals event to all clients on the channel."""
        event = format_patch_signals(signals)
        self._put(channel, event)

    def new(self, channel, *, presence_callback=None):
        """Create an empty channel. Idempotent.

        Args:
            presence_callback: Optional callable(user_ids: list[int]) -> str.
                Called on connect/disconnect to generate presence HTML.
        """
        registry.create(channel, presence_callback=presence_callback)

    def connect(self, channel, request, *, presence_callback=None):
        """Open an SSE stream for this request, register the user, and broadcast presence.

        Creates the channel if it doesn't exist. Cleans up and broadcasts updated
        presence automatically when the client disconnects.

        Can be called from a plain sync view — no async required.

        Returns a StreamingHttpResponse.
        """
        return async_to_sync(self._connect)(channel, request, presence_callback=presence_callback)

    async def _connect(self, channel, request, *, presence_callback=None):
        """Async implementation of connect."""
        registry.set_loop(asyncio.get_running_loop())
        registry.create(channel, presence_callback=presence_callback)

        queue = asyncio.Queue()
        user = await request.auser()
        self._add_user(channel, queue, user)

        async def event_stream():
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(
                            queue.get(), timeout=HEARTBEAT_INTERVAL
                        )
                        if event is _CLOSE:
                            return
                        yield event
                    except asyncio.TimeoutError:
                        yield HEARTBEAT
            except (asyncio.CancelledError, GeneratorExit):
                pass
            finally:
                self._remove_user(channel, queue)

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    def disconnect(self, channel, user_id):
        """Force-close all SSE connections for a user on a channel.

        Pushes a close sentinel into each of the user's queues. The stream
        generator exits cleanly and broadcasts updated presence to remaining users.
        """
        queues = registry.get_queues_for_user(channel, user_id)
        if not queues:
            return
        loop = registry.get_loop()
        if loop is None or loop.is_closed():
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        for queue in queues:
            if running_loop is loop:
                queue.put_nowait(_CLOSE)
            else:
                loop.call_soon_threadsafe(queue.put_nowait, _CLOSE)

    def kill(self, channel):
        """Destroy a channel, force-closing all connections."""
        queues = registry.get_queues(channel)
        if queues:
            loop = registry.get_loop()
            if loop and not loop.is_closed():
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None
                for queue in queues:
                    if running_loop is loop:
                        queue.put_nowait(_CLOSE)
                    else:
                        loop.call_soon_threadsafe(queue.put_nowait, _CLOSE)
        registry.destroy(channel)

    def get_users(self, channel):
        """Return list of user IDs (int) connected to a channel."""
        return registry.get_users(channel)

    def get_channels(self):
        """Return list of active channel names."""
        return registry.get_channels()

    def _add_user(self, channel, queue, user):
        """Register a user connection and broadcast updated presence."""
        user_id = user.pk if hasattr(user, "pk") else 0
        registry.add_user(channel, queue, user_id)
        self._broadcast_presence(channel)

    def _remove_user(self, channel, queue):
        """Unregister a user connection and broadcast updated presence."""
        registry.remove_user(channel, queue)
        if registry.get_queues(channel):
            self._broadcast_presence(channel)

    def _broadcast_presence(self, channel):
        """Broadcast the current presence list to all users on the channel.

        The presence callback may return:
        - str: HTML only (broadcast as datastar-patch-elements)
        - dict: signals only (broadcast as datastar-patch-signals)
        - (str, dict): HTML + signals (both broadcast)
        - (None, dict): signals only (tuple form)
        """
        config = registry.get_config(channel)
        callback = config.get("presence_callback")
        if callback is None:
            return

        user_ids = registry.get_users(channel)
        # Deduplicate (same user, multiple tabs)
        unique_ids = list(dict.fromkeys(user_ids))

        def _dispatch(result):
            if isinstance(result, tuple):
                html, signals = result
            elif isinstance(result, dict):
                html, signals = None, result
            else:
                html, signals = result, None

            if html:
                self._put(channel, format_patch_elements(html))
            if signals:
                self._put(channel, format_patch_signals(signals))

        # _broadcast_presence is called from _add_user/_remove_user which run
        # inside the async event loop (_connect is async). The callback may do
        # sync Django ORM work, which must not run on the event loop thread.
        # Schedule it as a Task using sync_to_async so it runs in a thread pool.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            from asgiref.sync import sync_to_async
            async def _run():
                result = await sync_to_async(callback)(channel, unique_ids)
                _dispatch(result)
            loop.create_task(_run())
        else:
            result = callback(channel, unique_ids)
            _dispatch(result)

    def _put(self, channel, event):
        """Push an event to all user queues on a channel.

        From async context (same event loop): puts directly.
        From sync context (thread pool): uses call_soon_threadsafe.
        Requires uvicorn or similar ASGI server with a persistent event loop.
        """
        queues = registry.get_queues(channel)
        if not queues:
            return

        loop = registry.get_loop()
        if loop is None or loop.is_closed():
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is loop:
            for queue in queues:
                queue.put_nowait(event)
        else:
            for queue in queues:
                loop.call_soon_threadsafe(queue.put_nowait, event)
