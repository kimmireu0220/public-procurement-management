# mock_exam — 필기 모의시험

회차별 **80문항**(1과목 30 · 2과목 20 · 3과목 30).

## 파일

| 파일 | 용도 |
|------|------|
| `필기_모의_문제.md` | 80문항 |
| `필기_모의_정답.md` | 정답·해설 |
| `index.html` | CBT 응시 UI |
| `필기_응시.html` | `index.html`과 동일 |
| `필기_모의_응시.html` | `index.html`과 동일 |
| `필기_풀이.md` | 채점·해설 (미응시 시 템플릿) |
| `교차검수.md` | 3단계 교차 검수 (응시 전) |
| `manifest.json` | 문항 ID (중복 방지) |
| `출제_방향.md` | (선택) A-0 출제 전 반영 요약 |
| `출제_피드백.md` | (선택) 응시 후 사용자 메모 — 〈K+1〉 A-0 입력 |
| `풀이/` | (선택) 재응시 시도 2+ (`필기_시도N_YYYY-MM-DD.md`) |
| `실기_모의_문제.md` | (선택) 실기 모의 |
| `실기_모의_정답.md` | (선택) 실기 채점 포인트 |
| [`오답노트.md`](오답노트.md) | 틀린 문항 누적 |

## 출제·풀이

- 프롬프트: [`docs/시험모의/`](../../docs/시험모의/) — [`선별.md`](../../docs/시험모의/선별.md) · [`풀이.md`](../../docs/시험모의/풀이.md)

회차 폴더 `〈K〉회차/`는 출제 시 생성한다.

### 출제 병합 · CBT · GitHub Pages (출제 완료 필수)

```bash
python3 tools/merge_mock_draft.py K
python3 tools/build_cbt_viewer.py --round K --pages   # HTML 3종 + docs/ 복사
# 이후 main 커밋·푸시 → Actions가 Pages 배포
cd output/mock_exam/〈K〉회차 && python3 -m http.server 8765   # 로컬 확인 (선택)
```

- `merge_mock_draft.py` — `_draft/*_선별.md` → 문제·정답·manifest (선별은 에이전트)
- `build_cbt_viewer.py` — CBT HTML 3종; `--pages` 시 `publish_cbt_pages.py` 동시 실행
- `publish_cbt_pages.py` — 최신 `〈K〉회차/index.html` → `docs/` (정답 md 제외)

**출제를 끝내면 반드시 `docs/`까지 갱신한 뒤 `main`에 push한다.** push 없이는 [온라인 CBT](https://kimmireu0220.github.io/public-procurement-management/)가 이전 회차로 남는다.

### GitHub Pages (온라인 CBT)

저장소 **Settings → Pages → Build from branch `main` / folder `/docs`**.  
배포 URL 루트(`…/public-procurement-management/`) = **가장 최신 회차** 필기 모의. 현재 메타: [`docs/cbt-meta.json`](../../docs/cbt-meta.json).  
`main` push 시 [`.github/workflows/deploy-cbt-pages.yml`](../../.github/workflows/deploy-cbt-pages.yml)이 `docs/` 변경을 배포한다.
