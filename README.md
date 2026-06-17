# public-procurement-management

공공조달관리사 교재 스캔 기반 문제집 추출·학습 파이프라인.

## 로컬 전용 자료 (Git 미포함)

용량 문제로 아래는 저장소에 올리지 않습니다. 각 기기에서 직접 보관하세요.

- `교재/<과목>/Chapter N/page_*.jpg` — 교재 스캔 이미지
- `표준 교재/<과목>/교재.pdf` — 원본 PDF

## 주요 경로

| 경로 | 내용 |
|---|---|
| `output/ocr/` | 1·3과목 OCR 텍스트 |
| `output/agent_extract/` | 추출 초안 (문제+정답) |
| `output/problem_book_final/` | 최종 문제집 (문제만) |
| `tools/` | OCR·빌드·감사 스크립트 |

## 설정

```bash
cp .env.example .env   # PROJECT_ROOT 등 수정
```
