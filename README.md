# ScholarTranslate

영어 학술 논문 PDF를 한국어로 번역하는 도구입니다. 번역은 외부 API 대신 Claude Code가 직접 수행하고, 이 저장소의 CLI는 그 앞뒤 단계(PDF 추출, 구조 검증, 출력 정리)를 맡습니다.

## 흐름

1. **추출**: `pdftotext`로 PDF를 읽어 문단 단위 원문 파일(`<PDF 이름>_en.txt`)을 만듭니다. 각 페이지 앞에 `p.N` 표시를 넣습니다.
2. **정리·번역**: Claude Code가 입력 파일의 머리말·꼬리말·참고문헌을 정리한 뒤, 문단마다 1:1로 번역해 `<PDF 이름>_ko.txt`에 씁니다. 번역 후 kr-style 스킬로 번역투를 다듬습니다. 절차는 `.claude/skills/translate-paper/SKILL.md`에 있습니다.
3. **검증**: 원문과 번역문의 `p.N` 표시와 페이지별 문단 수가 같은지 확인합니다.
4. **정리**: 비어 있지 않은 모든 줄 앞에 공백 2칸 들여쓰기를 붙입니다.

## 준비

- Python 3.12 이상, [uv](https://docs.astral.sh/uv/)
- poppler(`pdftotext`): `brew install poppler`

```bash
uv sync
cp glossary.json.example glossary.json   # 선택: 용어집
```

용어집 형식은 `[{"term": "...", "translation": "..."}]`입니다.

## 사용법

Claude Code에서 "이 논문 번역해줘"라고 PDF 경로와 함께 요청하면 아래 명령을 순서대로 실행합니다. 직접 실행할 수도 있습니다.

```bash
uv run thesis-translate extract paper.pdf --start-page 174   # → paper_en.txt
uv run thesis-translate verify paper_en.txt paper_ko.txt     # 구조 비교, 미번역 문단 경고
uv run thesis-translate format paper_ko.txt                  # 들여쓰기
```

`--start-page`에는 논문에 인쇄된 첫 페이지 번호를 넣습니다. 표지가 붙은 PDF는 `--first-pdf-page 2`로 건너뜁니다. 이미 있는 `_en.txt`는 `--force` 없이 덮어쓰지 않습니다. `verify`는 구조가 다르면 해당 페이지를 출력하고 종료 코드 1을 반환합니다.

## 라이선스

MIT
