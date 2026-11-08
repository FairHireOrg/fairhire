"""WSGI entrypoint for hosts without ASGI support (e.g. PythonAnywhere).

FastAPI is ASGI; a2wsgi adapts it so a WSGI server can serve it.
"""

from a2wsgi import ASGIMiddleware

from api import app as asgi_app

application = ASGIMiddleware(asgi_app)
