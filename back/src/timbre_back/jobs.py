class JobDeferred(Exception):
    """Raised by a job that should run again later; the worker keeps it queued."""
