from functools import lru_cache

from cobtainflow.file_memory import FileMemory


@lru_cache(maxsize=1)
def get_shared_memory() -> FileMemory:
    """Return a process-wide FileMemory instance (inherits CrewAI Memory)."""
    return FileMemory()
