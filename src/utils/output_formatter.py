"""Output formatting utility for translation results."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class OutputFormatter:
    """Utility class for formatting translation output files."""

    @staticmethod
    def format_output(file_path: str) -> None:
        """
        Format the output file by adding indentation to non-empty lines.

        Each non-empty line that doesn't start with spaces will be prefixed
        with two spaces for consistent indentation.

        Args:
            file_path: Path to the output file to format.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        output_path = Path(file_path)

        with output_path.open(encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            stripped = line.rstrip("\n")
            if stripped.strip() == "":
                # Keep empty lines as-is
                new_lines.append(line)
            elif not stripped.startswith("  "):
                # Add indentation to non-indented lines
                new_lines.append("  " + stripped + "\n")
            else:
                # Keep already indented lines as-is
                new_lines.append(line)

        with output_path.open("w", encoding="utf-8") as f:
            f.writelines(new_lines)

        logger.info(f"Output formatting completed for {file_path}")
