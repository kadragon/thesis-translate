"""Token counting utility for text chunking."""
# GENERATED FROM SPEC-TOKEN-COUNTER-001

import threading

import tiktoken


class TokenCounter:
    """Singleton utility for counting tokens in text using tiktoken encoding.

    This class implements the singleton pattern with thread-safe initialization
    to ensure only one encoding instance exists throughout the application
    lifecycle. The cl100k_base encoding (used by GPT models) is expensive to
    load, so caching it as a singleton improves performance.
    """

    _instance: "TokenCounter | None" = None
    _encoding: tiktoken.Encoding | None = None
    _lock = threading.Lock()

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC1
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC2
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC3
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC8
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC11
    def __new__(cls) -> "TokenCounter":
        """Create or return the singleton instance with thread-safe initialization.

        Uses double-check locking pattern to ensure thread safety while
        minimizing lock contention.

        Returns:
            The singleton TokenCounter instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking: verify again inside the lock
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Initialize encoding only once when the instance is created
                    cls._encoding = tiktoken.get_encoding("cl100k_base")
        return cls._instance

    def __init__(self) -> None:
        """Initialization is handled in __new__ to ensure it runs only once."""
        # No-op: all initialization happens in __new__

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC4
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC5
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC6
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC7
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC9
    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC10
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens in the text.

        Raises:
            AssertionError: If encoding failed to initialize (should not occur).
        """
        assert self._encoding is not None, "Encoding failed to initialize"
        return len(self._encoding.encode(text))
