# Academic Paper Translator

This project provides a tool for translating English academic papers into Korean, leveraging the OpenAI API.

## Features

- **Text Preprocessing**: Cleans text copied from the clipboard, handling common issues like hyphens and extra spaces.
- **Chunked Translation**: Translates large documents by splitting them into smaller, manageable chunks to optimize API usage.
- **OpenAI API Integration**: Utilizes OpenAI's GPT models for high-quality, academic-style Korean translation.
- **Customizable Glossary**: Supports a user-defined glossary (via `glossary.json`) to ensure consistent translation of specific academic terms.
- **Output Formatting**: Formats the translated output for better readability.

## Project Structure

- `main.py`: The main entry point for running the entire translation workflow.
- `core/`:
  - `file_translator.py`: Manages reading, chunking, and writing translated content.
  - `openai_translator.py`: Handles communication with the OpenAI API for translation, including glossary integration.
- `utils/`:
  - `text_preprocessor.py`: Provides functionality for cleaning and preparing text from the clipboard.
  - `format_output.py`: Contains utilities for post-processing the translated text (e.g., adding leading spaces).
- `glossary.json`: A JSON file to define custom academic terms and their Korean translations.
- `_trimed_text.txt`: An intermediate file storing the preprocessed English text.
- `_result_text_ko.txt`: The final output file containing the Korean translation.

## Setup and Usage

### Prerequisites

- Python 3.x
- An OpenAI API Key

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-repo/academic-paper-translator.git
   cd academic-paper-translator
   ```

2. Install the required Python packages:

   ```bash
   pip install openai python-dotenv clipboard
   ```

### Configuration

1. **OpenAI API Key**: Create a `.env` file in the project root directory and add your OpenAI API key:

   ```
   OPENAI_API_KEY="your_openai_api_key_here"
   ```

2. **Glossary**: Edit the `glossary.json` file in the project root to include any specific academic terms and their desired Korean translations. The format is an array of objects, each with `"term"` and `"translation"` keys.

### Running the Translator

1. Run the main script:

   ```bash
   python main.py
   ```

2. Follow the prompts in the console. You will be asked to copy text to your clipboard and then the script will process and translate it.

## Contributing

Feel free to fork the repository, open issues, or submit pull requests.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
