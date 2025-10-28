"""Text preprocessing utilities for managing and preparing text for translation."""
# GENERATED FROM SPEC-TEXT-PREP-001

import logging
from pathlib import Path

import clipboard

from src import config

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """Manages text input from clipboard and saves to file for translation."""

    FILE_NAME: str = config.INPUT_FILE

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC1
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC2
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC3
    def __init__(self) -> None:
        """Initialize text preprocessor."""
        self.text: str = ""
        self.page_number: int | None = None

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

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC4
    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC5
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

            order = input(
                "번역을 진행하시겠습니까? [A:추가 / B:종료 / E:페이지번호추가 /"
                " Enter:진행]"
            ).upper()
            if order == "A":
                self.add_text_from_clipboard()
            elif order in ("", "C"):
                self.add_text_from_clipboard()
                self._clean_text()

                self.add_text_to_file(self.text)
                self.text = ""
            elif order == "B":
                break
            elif order == "E":
                self.add_text_to_file(f"p.{self.page_number}")
                self.page_number += 1
