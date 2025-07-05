# Gemini Project Analysis

## Project Overview

This project appears to be a tool for translating English academic papers into Korean. It utilizes the OpenAI API for translation and includes functionalities for text preprocessing and file handling.

## Core Components

- **`utils/text_preprocessor.py`**: This script captures text from the clipboard, performs cleaning operations (like removing hyphens and extra spaces), and saves the processed text to `_trimed_text.txt`. It has an interactive command-line interface.
- **`core/file_translator.py`**: This module reads the text from `_trimed_text.txt`, splits it into chunks based on a maximum token length, and sends each chunk to a translator. It's designed to handle large files by processing them in smaller, manageable blocks.
- **`core/openai_translator.py`**: This is the translation engine. It uses the OpenAI API (specifically, a GPT model like "gpt-4.1-mini") to translate the text chunks from English to Korean. It loads a glossary of academic terms from `glossary.json` to ensure translation consistency. The prompt is engineered to produce formal, academic-style Korean.
- **`utils/format_output.py`**: A utility script to add leading spaces to each line in `_result_text_ko.txt` for formatting purposes.
- **`main.py`**: The main entry point of the application. It orchestrates the text preprocessing, translation, and output formatting steps.

## Workflow

1. The user runs `main.py`.
2. `main.py` first invokes `utils/text_preprocessor.py` to gather and clean text from the clipboard, appending it to `_trimed_text.txt`.
3. Then, `main.py` initiates the translation process using `core/file_translator.py`. This reads `_trimed_text.txt`, and uses `core/openai_translator.py` to translate the content chunk by chunk.
4. The Korean translation is saved to `_result_text_ko.txt` (the default output file).
5. Finally, `main.py` calls `utils/format_output.py` to format the output file.

## Dependencies

- `openai`: For accessing the OpenAI API.
- `python-dotenv`: To manage environment variables (like API keys).
- `clipboard`: To read from the system clipboard.

## Key Files

- **`_trimed_text.txt`**: The intermediate file containing the cleaned English text ready for translation.
- **`_result_text_ko.txt`**: The final output file with the Korean translation.
- **`glossary.json`**: A JSON file containing academic terms and their Korean translations, used by `core/openai_translator.py`.
- **`.gitignore`**: Standard Python gitignore file.

## How to Run

1. Install dependencies: `pip install openai python-dotenv clipboard`
2. Create a `.env` file with your `OPENAI_API_KEY`.
3. Ensure `glossary.json` is present in the project root with your desired glossary terms.
4. Run the main script: `python main.py`
