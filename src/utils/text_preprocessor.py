"""Text preprocessing utilities for managing and preparing text for translation."""
# GENERATED FROM SPEC-TEXT-PREP-001
# GENERATED FROM SPEC-USER-PROMPTED-001

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import clipboard

from src import config

if TYPE_CHECKING:
    from src.core.concurrent_orchestrator import ConcurrentTranslationOrchestrator

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """Manages text input from clipboard and saves to file for translation."""

    FILE_NAME: str = config.INPUT_FILE

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC1
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC2
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC3
    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
    def __init__(
        self,
        orchestrator: "ConcurrentTranslationOrchestrator | None" = None,
    ) -> None:
        """Initialize text preprocessor.

        Args:
            orchestrator: Optional ConcurrentOrchestrator for translation status.
        """
        self.text: str = ""
        self.page_number: int | None = None
        self.orchestrator = orchestrator

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC4
    def add_text_to_file(self, text: str, file_name: str = FILE_NAME) -> None:
        """Append the given text to the specified file.

        Args:
            text: Text to append to the file.
            file_name: Path to the file (default: configured input file).
        """
        with Path(file_name).open("a", encoding="UTF-8") as f:
            f.write("  " + text + "\n\n")

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC2
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC6
    def add_text_from_clipboard(self) -> None:
        """Add text from the clipboard to the current text."""
        try:
            clipboard_data = clipboard.paste()
            self.text += clipboard_data + "\n"

        except Exception as exc:  # pragma: no cover - exercised via mock
            logger.warning(
                "클립보드에서 텍스트를 불러오지 못했습니다. 수동 입력을 시도하세요.",
                exc_info=exc,
            )

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC3
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC7
    def _clean_text(self) -> None:
        """Clean and merge the current text."""
        try:
            merged_text = ""

            for line in self.text.split("\n"):
                merged_text += line.strip() + " "

            merged_text = merged_text.replace("- ", "")

            self.text = merged_text.strip()

        except Exception as exc:  # pragma: no cover - exercised via mock
            logger.warning(
                "텍스트 정리 중 오류가 발생했습니다. 입력을 확인한 뒤 다시 시도하세요.",
                exc_info=exc,
            )

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
    def _display_translation_status(self) -> str:
        """Display translation status if orchestrator is available.

        Returns:
            Additional menu text with translation status.
        """
        if self.orchestrator is None:
            return ""

        ready, token_count = self.orchestrator.is_translation_ready()
        if ready:
            return f" / T:번역시작({token_count} tokens)"
        return ""

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC3
    def _handle_translation_trigger(self) -> bool:
        """Handle 'T' key to trigger translation.

        Returns:
            True if translation was triggered, False otherwise.
        """
        if self.orchestrator is None:
            return False

        success = self.orchestrator.trigger_translation_manual()
        if success:
            print("번역을 시작합니다...")  # noqa: T201
            return True
        print("번역 가능한 컨텐츠가 없습니다.")  # noqa: T201
        return False

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC6
    def _handle_exit_confirmation(self) -> bool:
        """Handle exit confirmation when translation is ready.

        Returns:
            True if user confirms exit, False to continue.
        """
        if self.orchestrator is None:
            return True

        ready, token_count = self.orchestrator.is_translation_ready()
        if ready:
            confirm = input(
                f"번역 가능한 컨텐츠가 있습니다 ({token_count} tokens). "
                "정말 종료하시겠습니까? [Y/N]: "
            ).upper()
            return confirm == "Y"
        return True

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC4
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC5
    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC3
    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC6
    def run(self) -> None:
        """Run the main loop for managing text translation."""
        while True:
            if self.page_number is None:
                while True:
                    try:
                        start_page = input("시작 페이지 번호를 입력하세요: ")
                        if start_page.isnumeric():
                            self.page_number = int(start_page)
                            break

                    except ValueError:
                        pass

            # Build menu with translation status
            translation_status = self._display_translation_status()
            menu_prompt = (
                f"번역을 진행하시겠습니까? "
                f"[A:추가 / B:종료 / E:페이지번호추가 / Enter:진행"
                f"{translation_status}]: "
            )

            order = input(menu_prompt).upper()
            if order == "A":
                self.add_text_from_clipboard()
            elif order in ("", "C"):
                self.add_text_from_clipboard()
                self._clean_text()

                self.add_text_to_file(self.text)
                self.text = ""
            elif order == "B":
                if self._handle_exit_confirmation():
                    break
            elif order == "E":
                self.add_text_to_file(f"p.{self.page_number}")
                self.page_number += 1
            elif order == "T":
                self._handle_translation_trigger()
