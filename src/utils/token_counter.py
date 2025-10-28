"""Token counting utility for text chunking."""

import tiktoken


class TokenCounter:
    """Utility class for counting tokens in text using tiktoken encoding."""

    _instance = None
    _encoding = None

    def __new__(cls) -> "TokenCounter":
        """Singleton pattern to ensure only one encoding instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the token counter with cl100k_base encoding."""
        if TokenCounter._encoding is None:
            TokenCounter._encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens in the text.
        """
        return len(TokenCounter._encoding.encode(text))
