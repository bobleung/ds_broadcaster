import asyncio
import threading


class ChannelRegistry:
    """Thread-safe in-memory registry of channels and their user queues."""

    def __init__(self):
        self._channels: dict[str, set[asyncio.Queue]] = {}
        self._channel_config: dict[str, dict] = {}
        self._queue_info: dict[asyncio.Queue, int] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop):
        """Store reference to the ASGI event loop. Called on first SSE connect."""
        self._loop = loop

    def get_loop(self):
        return self._loop

    def create(self, channel, **config):
        """Create channel if it doesn't exist. Idempotent.

        Optional config is stored with the channel (e.g. presence_callback).
        Config is only written on first creation; subsequent calls are no-ops.
        """
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
                if config:
                    self._channel_config[channel] = config

    def destroy(self, channel):
        """Remove channel and all its users."""
        with self._lock:
            queues = self._channels.pop(channel, set())
            for q in queues:
                self._queue_info.pop(q, None)
            self._channel_config.pop(channel, None)

    def get_config(self, channel):
        """Return config dict for a channel, or empty dict."""
        with self._lock:
            return self._channel_config.get(channel, {})

    def add_user(self, channel, queue, user_id):
        """Add user to channel, creating channel if needed.

        user_id is an int (the user's primary key).
        """
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(queue)
            self._queue_info[queue] = user_id

    def remove_user(self, channel, queue):
        """Remove user from channel. Remove channel if empty."""
        with self._lock:
            users = self._channels.get(channel)
            if users is not None:
                users.discard(queue)
                if not users:
                    del self._channels[channel]
            self._queue_info.pop(queue, None)

    def get_channels(self):
        """Return list of active channel names."""
        with self._lock:
            return list(self._channels.keys())

    def get_queues(self, channel):
        """Return a snapshot (list copy) of queues for a channel."""
        with self._lock:
            queues = self._channels.get(channel)
            if queues is None:
                return []
            return list(queues)

    def get_users(self, channel):
        """Return list of user IDs (int) for a channel."""
        with self._lock:
            queues = self._channels.get(channel)
            if queues is None:
                return []
            return [
                self._queue_info[q]
                for q in queues
                if q in self._queue_info
            ]

    def get_queues_for_user(self, channel, user_id):
        """Return queues belonging to a specific user on a channel."""
        with self._lock:
            queues = self._channels.get(channel)
            if queues is None:
                return []
            return [
                q for q in queues
                if self._queue_info.get(q) == user_id
            ]


registry = ChannelRegistry()
