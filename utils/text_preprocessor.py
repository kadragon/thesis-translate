"""This module provides the Trimer class for managing and translating text."""


import clipboard


class TextPreprocessor:
    """Class for managing and translating text."""
    FILE_NAME = '_trimed_text.txt'

    def __init__(self):
        self.text = ""

    def add_text_to_file(self, text: str, file_name: str = FILE_NAME):
        """Append the given text to the specified file."""
        with open(file_name, 'a', encoding="UTF-8") as f:
            f.write("  " + text + "\n\n")

    def add_text_from_clipboard(self) -> None:
        """Add text from the clipboard to the current text."""
        try:
            clipboard_data = clipboard.paste()
            self.text += clipboard_data + "\n"
            print("현재 관리된 텍스트: " + self.text)
        except Exception as e:
            print(f"Clipboard Error: {str(e)}")

    def make_clean_text(self) -> None:
        """Clean and merge the current text."""
        try:
            merged_text = ""

            for line in self.text.split("\n"):
                merged_text += line.strip() + ' '

            merged_text = merged_text.replace('- ', '')

            self.text = merged_text.strip()

            print("정리된 텍스트: " + self.text)
        except Exception as e:
            print(f"Clipboard Error: {str(e)}")

    def run(self) -> None:
        """Run the main loop for managing text translation."""
        while True:
            order = input(
                "번역을 진행하시겠습니까? [A:추가 / B:종료 / 숫자:페이지 / Enter:진행]").upper()
            if order == 'A':
                self.add_text_from_clipboard()
            elif order == '' or order == 'C':
                self.add_text_from_clipboard()
                self.make_clean_text()

                if order == 'C':
                    self.add_text_to_file('  ' + self.text)
                else:
                    self.add_text_to_file(self.text)
                self.text = ""
            elif order == 'B':
                break
            elif order.isnumeric():
                self.add_text_to_file('p.' + order)
