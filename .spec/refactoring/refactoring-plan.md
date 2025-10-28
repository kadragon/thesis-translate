# 리팩토링 계획: Batch 기능 제거 및 구조 개선

**Intent**: Batch API 기능을 제거하고, 코드 중복을 제거하며, 전체 구조를 개선합니다.

**Scope**:
- ✅ `batch_translator.py` 삭제
- ✅ `BATCH_INPUT_FILE` 설정 제거
- ✅ 공유 유틸리티 추출 (`token_counter.py`, `formatter.py`)
- ✅ 모든 모듈에 타입 힌트 추가
- ✅ 설정 구조 통합

---

## 1️⃣ 현재 구조

```
src/
├── __init__.py
├── config.py                    (9 lines)
├── main.py                      (49 lines)
├── core/
│   ├── __init__.py
│   ├── translation_config.py    (73 lines)
│   ├── batch_translator.py      (147 lines) ❌ 삭제 대상
│   └── normal_translator.py     (113 lines)
└── utils/
    ├── __init__.py
    └── text_preprocessor.py     (85 lines)
```

---

## 2️⃣ 목표 구조

```
src/
├── __init__.py
├── config.py                    (개선됨)
├── main.py                      (단순화)
├── core/
│   ├── __init__.py
│   ├── translator.py            (개선된 NormalTranslator, 타입 힌트 추가)
│   └── translation_config.py    (간단히 함)
└── utils/
    ├── __init__.py
    ├── text_preprocessor.py
    ├── token_counter.py         (추출된 공유 유틸)
    └── formatter.py             (추출된 공유 유틸)
```

---

## 3️⃣ 상세 작업 항목

### A. 공유 유틸리티 추출

#### `utils/token_counter.py` (신규)
- `TokenCounter` 클래스
- `count_tokens(text: str) -> int` 메서드
- Tiktoken 인코딩 초기화 (싱글톤 패턴)

#### `utils/formatter.py` (신규)
- `OutputFormatter` 클래스
- `format_output(file_path: str) -> None` 메서드
- 들여쓰기 로직 통일

### B. `config.py` 정리
```python
# 유지할 항목
OPENAI_MODEL = "gpt-5-mini"
TEMPERATURE = 1
MAX_TOKEN_LENGTH = 8000
INPUT_FILE = "_trimmed_text.txt"
OUTPUT_FILE = "_result_text_ko.txt"
GLOSSARY_FILE = "glossary.json"

# 삭제할 항목
# BATCH_INPUT_FILE = "batch_input.jsonl"  ❌ 제거
```

### C. `core/translator.py` (기존 normal_translator.py 개선)
- `NormalTranslator` 클래스 이름 유지
- `TokenCounter` 임포트 및 사용
- `OutputFormatter` 임포트 및 사용
- 타입 힌트 완성
  - `translate(self) -> None`
  - `_translate_chunk(self, text: str) -> str`
  - `format_output(self) -> None`

### D. `core/translation_config.py` 단순화
- `client` 생성 제거 (불필요함)
- 타입 힌트 추가
- docstring 개선

---

## 4️⃣ 코드 중복 제거

### 현재 중복되는 부분

| 코드 | 위치 | 대체책 |
|------|------|---------|
| `_count_tokens()` | batch_translator.py, normal_translator.py | `TokenCounter.count_tokens()` |
| `format_output()` | batch_translator.py, normal_translator.py | `OutputFormatter.format_output()` |
| tiktoken 초기화 | 양쪽 모두 | `TokenCounter` 싱글톤 |

---

## 5️⃣ 타입 힌트 추가 체크리스트

- [ ] `config.py`: 모든 상수에 타입 명시
- [ ] `translation_config.py`: 메서드 반환 타입 추가
- [ ] `translator.py`: 모든 public/private 메서드에 타입 힌트
- [ ] `text_preprocessor.py`: 타입 힌트 추가
- [ ] `token_counter.py`: 새 모듈 타입 힌트
- [ ] `formatter.py`: 새 모듈 타입 힌트
- [ ] `main.py`: 함수 시그니처 개선

---

## 6️⃣ 테스트 업데이트

### 삭제할 테스트
- ❌ `tests/test_batch_translator.py` (해당 파일 없음, 참고용)

### 업데이트할 테스트
- `tests/test_normal_translator.py` → `tests/test_translator.py`로 이름 변경
- `TokenCounter` 테스트 추가
- `OutputFormatter` 테스트 추가

---

## 7️⃣ 마이그레이션 단계

### Phase 1: 새 유틸리티 생성
1. `utils/token_counter.py` 생성
2. `utils/formatter.py` 생성
3. 기존 코드에서 로직 추출 및 검증

### Phase 2: 메인 모듈 개선
1. `config.py` 정리 (BATCH_INPUT_FILE 제거)
2. `core/translation_config.py` 타입 힌트 추가
3. `core/translator.py` 생성 (normal_translator.py → 이름 변경)
4. 공유 유틸 임포트 적용

### Phase 3: 정리
1. `batch_translator.py` 삭제
2. 기존 `normal_translator.py` 삭제 (새 `translator.py`로 통합됨)
3. `main.py` 업데이트 (임포트 경로 수정)

### Phase 4: 테스트 및 검증
1. 모든 테스트 업데이트
2. 타입 체킹 (`mypy`) 실행
3. 통합 테스트 실행
4. 빌드 확인

---

## 8️⃣ 예상 개선 효과

| 항목 | 이전 | 이후 | 개선 |
|------|------|------|------|
| 모듈 수 | 9 | 11 (+유틸) | ✅ |
| 중복 코드 | 있음 | 없음 | ✅ |
| 타입 힌트 | 낮음 | 높음 | ✅ |
| 유지보수성 | 중간 | 높음 | ✅ |
| 테스트 커버리지 | 낮음 | 높음 | ✅ |

---

## 9️⃣ 위험 요소 및 대응책

| 위험 | 대응책 |
|------|--------|
| 공유 유틸 추출 시 버그 발생 | 동등한 로직 테스트로 검증 |
| 임포트 경로 오류 | 린터 및 타입 체크 실행 |
| 기능 손실 | batch_translator.py 삭제 전 모든 테스트 통과 |

---

## 🔟 최종 검증 항목

- [ ] 모든 테스트 통과 (pytest)
- [ ] 타입 체크 통과 (mypy)
- [ ] 린팅 통과 (ruff)
- [ ] 커버리지 요구사항 충족 (80% 이상)
- [ ] Git 커밋 메시지에 SPEC-ID 포함

---

## 📊 작업 예상 시간

- Phase 1: 30분 (유틸 추출)
- Phase 2: 45분 (메인 모듈 개선)
- Phase 3: 15분 (정리)
- Phase 4: 30분 (테스트 및 검증)
- **총 2시간**

---

**Status**: 계획 수립 완료 ✅
**Next Step**: Phase 1 시작 (utils/token_counter.py 생성)
