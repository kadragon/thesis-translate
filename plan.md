# Plan

- [x] ask_menu_action accepts lowercase "a" and returns "A"
- [x] ask_menu_action accepts lowercase "e" and returns "E"
- [x] ask_menu_action accepts lowercase "b" and returns "B"
- [x] prompt instructs to output only translated text (no source text)
- [x] merge tiny last chunk into previous even if it exceeds max_token_length
- [x] chunk merge respects max_token_length constraint
- [ ] refactor: extract chunk merge logic from chunk_generator to translate method
