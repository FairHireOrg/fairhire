"""WSGI entrypoint for hosts without ASGI support (e.g. PythonAnywhere).

FastAPI is ASGI; a2wsgi adapts it so a WSGI server can serve it.
"""

import os

from a2wsgi import ASGIMiddleware

from api import app as asgi_app

# a2wsgi starts its event-loop thread when constructed. uWSGI imports this
# module in the master and then forks workers, and threads don't survive a
# fork, so build the middleware lazily inside each worker process.
_middleware = None
_pid = None


def application(environ, start_response):
    global _middleware, _pid
    if _middleware is None or _pid != os.getpid():
        _middleware = ASGIMiddleware(asgi_app)
        _pid = os.getpid()
    return _middleware(environ, start_response)
