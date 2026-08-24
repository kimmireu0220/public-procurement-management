---
name: gpt-sovits-korean-lecture
description: 허가된 참조 음성으로 공공조달관리사 한국어 강의 대본을 만들거나 다듬고 GPT-SoVITS V2로 로컬 MP3·WAV를 합성한다. 짧은 음성, 장문 내레이션, 구간별 강의 음성을 만들 때 사용한다.
---

# GPT-SoVITS Korean Lecture

사용자의 학습 목적에 맞는 한국어 강의 대본과 로컬 음성을 만든다. 목차, 분량, 설명 방식,
문제·퀴즈 포함 여부와 출력 파일 구성은 작업에 맞춰 자유롭게 정한다. 사용자가 준 최종
대본은 재작성 요청이 없는 한 내용과 순서를 보존한다.

## 필수 안전 규칙

- 참조 음성의 소유·라이선스 또는 화자의 명시적 합성 허가를 확인한다.
- 사칭, 사기, 기만, 괴롭힘, 허가 없는 공인 모사와 음성 인증 우회에는 사용하지 않는다.
- 권한을 확인한 뒤에만 생성기에 `--confirm-authorized`를 전달한다.
- 로컬 합성 허가가 참조 음성의 외부 업로드나 결과물 공개까지 포함한다고 가정하지 않는다.
  클라우드 전송 또는 공개가 필요하면 그 범위의 권한을 따로 확인한다.

## 작업 선택

- 강의 내용의 정확성과 공개 범위는 프로젝트 루트의 `AGENTS.md`를 따른다.
- 대본은 새로 쓰거나 기존 문서를 그대로 합성할 수 있다. 영어·숫자를 한글 발음으로
  풀어쓰는 작업은 발음 개선에 도움이 될 때만 하며 의미와 사용자의 원문 의도를 보존한다.
- `scripts/generate_gpt_sovits.py`에 `--text`, `--file`, `--stdin` 중 편한 입력을 사용한다.
- 장문은 같은 출력 경로를 사용하면 유효한 캐시를 재사용할 수 있다.
- 절별 파일이 유용한 경우에만 `SECTION_START` 표시와 `--split-sections`를 사용한다.
- 공공조달 Part 전체를 구성하거나 구간 분할 형식이 필요할 때만
  [references/procurement-part-workflow.md](references/procurement-part-workflow.md)를 읽는다.

## 실행 예시

프로젝트 루트에서 실행한다.

```bash
python3 .agents/skills/gpt-sovits-korean-lecture/scripts/generate_gpt_sovits.py \
  --file /absolute/path/lecture.txt \
  --ref-audio /absolute/path/reference.wav \
  --ref-text-file /absolute/path/reference-transcript.txt \
  --output output/gpt_sovits_audio/lecture.mp3 \
  --confirm-authorized
```

기본 로컬 런타임은 `/Users/kimmireu/.cache/codex-gpt-sovits`이며 필요하면
`GPT_SOVITS_RUNTIME` 또는 `--repo`로 바꿀 수 있다. 참조 음성의 길이·포맷과 출력 형식은
생성기 도움말과 실제 품질을 보고 선택한다.

## 결과 전달

- 생성된 음성은 Codex에서 재생할 수 있도록 절대 경로로 제공한다.
- 여러 파일이면 순서와 저장 위치를 알린다.
- 실패한 청크나 생략된 구간이 있으면 숨기지 않고 알린다.
