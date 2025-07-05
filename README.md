# ScholarTranslate

이 프로젝트는 OpenAI API를 활용하여 영어 학술 논문을 한국어로 번역하는 도구입니다.

## 주요 기능

- **텍스트 전처리**: 클립보드에서 복사한 텍스트를 정리하고, 하이픈이나 불필요한 공백과 같은 일반적인 문제를 처리합니다.
- **분할 번역**: 대용량 문서를 작고 관리하기 쉬운 청크로 분할하여 API 사용을 최적화하고 번역합니다.
- **OpenAI API 연동**: OpenAI의 GPT 모델을 활용하여 고품질의 학술적인 한국어 번역을 제공합니다.
- **사용자 정의 용어집**: `glossary.json` 파일을 통해 사용자 정의 용어집을 지원하여 특정 학술 용어의 일관된 번역을 보장합니다.
- **출력 형식 지정**: 번역된 결과물의 가독성을 높이기 위해 형식을 지정합니다.

## 프로젝트 구조

- `main.py`: 전체 번역 워크플로우를 실행하는 주요 진입점입니다.
- `core/`:
  - `file_translator.py`: 번역할 내용을 읽고, 청크로 분할하며, 번역된 내용을 작성하는 것을 관리합니다.
  - `openai_translator.py`: 용어집 통합을 포함하여 OpenAI API와의 통신을 처리합니다.
- `utils/`:
  - `text_preprocessor.py`: 클립보드에서 텍스트를 정리하고 준비하는 기능을 제공합니다.
  - `format_output.py`: 번역된 텍스트를 후처리하는 유틸리티(예: 선행 공백 추가)를 포함합니다.
- `glossary.json`: 사용자 정의 학술 용어와 해당 한국어 번역을 정의하는 JSON 파일입니다.
- `_trimed_text.txt`: 전처리된 영어 텍스트를 저장하는 중간 파일입니다.
- `_result_text_ko.txt`: 한국어로 번역된 최종 결과물 파일입니다.

## 설정 및 사용법

### 필수 요구 사항

- Python 3.x
- OpenAI API 키

### 설치

1.  저장소를 클론합니다:
    ```bash
    git clone https://github.com/your-repo/academic-paper-translator.git
    cd academic-paper-translator
    ```
2.  필요한 Python 패키지를 설치합니다:
    ```bash
    pip install openai python-dotenv clipboard
    ```

### 설정

1.  **OpenAI API 키**: 프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 OpenAI API 키를 추가합니다:
    ```
    OPENAI_API_KEY="your_openai_api_key_here"
    ```
2.  **용어집**: 프로젝트 루트에 있는 `glossary.json` 파일을 편집하여 특정 학술 용어와 원하는 한국어 번역을 포함시킵니다. 형식은 각 항목이 `"term"` 및 `"translation"` 키를 가진 객체 배열입니다.

### 번역기 실행

1.  메인 스크립트를 실행합니다:
    ```bash
    python main.py
    ```
2.  콘솔의 지시에 따릅니다. 텍스트를 클립보드에 복사하도록 요청받으며, 스크립트가 이를 처리하고 번역합니다.

## 기여

자유롭게 저장소를 포크하고, 이슈를 열거나, 풀 리퀘스트를 제출해 주세요.

## 라이선스

이 프로젝트는 MIT 라이선스에 따라 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.