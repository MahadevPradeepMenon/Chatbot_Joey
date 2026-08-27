"""FastAPI backend package for Hey Joey."""

# Re-export the default FastAPI application and its factory so callers can
# import the package-level API without depending on the internal module path.
from api.main import app, create_app

# Define the public names intentionally exposed by this package.
__all__ = [
    "app",
    "create_app",
]