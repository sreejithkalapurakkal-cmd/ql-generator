"""Context variables for passing user identity into synchronous co-pilot DB tools.

asyncio.to_thread automatically propagates contextvars to the spawned thread,
so these values set before the agent call are available inside the sync tools.
"""
import contextvars

current_user_id = contextvars.ContextVar('current_user_id', default=None)
current_user_is_admin = contextvars.ContextVar('current_user_is_admin', default=False)
