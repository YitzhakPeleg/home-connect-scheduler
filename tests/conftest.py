import os

# Set required env vars before any imports that trigger Settings
os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("USE_SIMULATOR", "true")
