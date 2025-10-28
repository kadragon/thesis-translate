# GENERATED FROM SPEC-TOKEN-COUNTER-001

import threading

from src.utils.token_counter import TokenCounter

MIN_TOKEN_COUNT = 100
THREAD_COUNT = 10


class TestTokenCounter:
    """Test suite for TokenCounter singleton class."""

    def setup_method(self) -> None:
        """Reset singleton state before each test."""
        # Reset the singleton instance for isolated tests
        TokenCounter._instance = None
        TokenCounter._encoding = None

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC1
    def test_singleton_returns_same_instance(self) -> None:
        """AC-1: GIVEN TokenCounter WHEN creating multiple instances THEN same
        object is returned."""
        # When
        counter1 = TokenCounter()
        counter2 = TokenCounter()

        # Then
        assert counter1 is counter2
        assert id(counter1) == id(counter2)

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC2
    def test_encoding_initialized_on_first_instantiation(self) -> None:
        """AC-2: GIVEN TokenCounter WHEN first instance is created THEN encoding
        is initialized."""
        # When
        counter = TokenCounter()

        # Then
        assert TokenCounter._encoding is not None
        assert counter._encoding is not None

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC3
    def test_encoding_not_reinitialized(self) -> None:
        """AC-3: GIVEN TokenCounter singleton WHEN multiple instances are created
        THEN encoding is not reloaded."""
        # Given
        TokenCounter()
        encoding_id_1 = id(TokenCounter._encoding)

        # When
        TokenCounter()
        encoding_id_2 = id(TokenCounter._encoding)

        # Then
        assert encoding_id_1 == encoding_id_2

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC4
    def test_count_tokens_basic(self) -> None:
        """AC-4: GIVEN text WHEN counting tokens THEN correct number is returned."""
        # Given
        counter = TokenCounter()

        # When
        token_count = counter.count_tokens("Hello world")

        # Then
        assert isinstance(token_count, int)
        assert token_count > 0

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC5
    def test_count_tokens_empty_string(self) -> None:
        """AC-5: GIVEN empty string WHEN counting tokens THEN zero is returned."""
        # Given
        counter = TokenCounter()

        # When
        token_count = counter.count_tokens("")

        # Then
        assert token_count == 0

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC6
    def test_count_tokens_long_text(self) -> None:
        """AC-6: GIVEN long text WHEN counting tokens THEN returns reasonable count."""
        # Given
        counter = TokenCounter()
        long_text = "Hello world. " * 100

        # When
        token_count = counter.count_tokens(long_text)

        # Then
        assert token_count > MIN_TOKEN_COUNT  # Should be significantly more tokens

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC7
    def test_count_tokens_consistency(self) -> None:
        """AC-7: GIVEN same text WHEN counting tokens multiple times THEN results
        are consistent."""
        # Given
        counter = TokenCounter()
        text = "The quick brown fox jumps over the lazy dog"

        # When
        count1 = counter.count_tokens(text)
        count2 = counter.count_tokens(text)

        # Then
        assert count1 == count2

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC8
    def test_thread_safe_initialization(self) -> None:
        """AC-8: GIVEN concurrent threads WHEN initializing TokenCounter THEN only
        one instance is created."""
        # Reset for this test
        TokenCounter._instance = None
        TokenCounter._encoding = None

        instances = []
        lock = threading.Lock()

        def create_instance() -> None:
            """Create TokenCounter instance and store it."""
            counter = TokenCounter()
            with lock:
                instances.append(counter)

        # When: Create multiple threads that instantiate TokenCounter
        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Then: All instances should be the same object
        assert len(instances) == THREAD_COUNT
        assert all(instance is instances[0] for instance in instances)
        assert all(id(instance) == id(instances[0]) for instance in instances)

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC9
    def test_count_tokens_with_special_characters(self) -> None:
        """AC-9: GIVEN text with special characters WHEN counting tokens THEN
        handles correctly."""
        # Given
        counter = TokenCounter()

        # When
        token_count = counter.count_tokens("Hello, world! @#$%^&*()")

        # Then
        assert isinstance(token_count, int)
        assert token_count > 0

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC10
    def test_count_tokens_with_unicode(self) -> None:
        """AC-10: GIVEN text with unicode characters WHEN counting tokens THEN
        handles correctly."""
        # Given
        counter = TokenCounter()

        # When
        token_count = counter.count_tokens("Hello 안녕하세요 世界 🌍")

        # Then
        assert isinstance(token_count, int)
        assert token_count > 0

    # Trace: SPEC-TOKEN-COUNTER-001, TEST-TOKEN-COUNTER-001-AC11
    def test_multiple_counters_share_encoding(self) -> None:
        """AC-11: GIVEN multiple counter instances WHEN using different instances
        THEN encoding is shared."""
        # Given
        counter1 = TokenCounter()
        text = "Test text"
        count1 = counter1.count_tokens(text)

        # When
        counter2 = TokenCounter()
        count2 = counter2.count_tokens(text)

        # Then
        assert count1 == count2
        assert counter1._encoding is counter2._encoding
