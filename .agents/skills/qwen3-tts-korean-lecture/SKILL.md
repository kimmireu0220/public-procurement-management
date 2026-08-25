---
name: qwen3-tts-korean-lecture
description: Qwen3-TTS 공식 Sohee 화자로 공공조달관리사 한국어 강의 대본을 만들거나 다듬고 로컬 MP3·WAV를 합성한다. 짧은 샘플, 장문 내레이션, 구간별 강의 음성 제작에 사용한다.
---

# Qwen3-TTS Korean Lecture

한국어 강의 대본을 만들고 Qwen3-TTS의 내장 `Sohee` 화자로 로컬 음성을 합성한다.
이 프로젝트의 기본 음성 엔진은 `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`이며,
참조 음성 복제 없이 내장 화자를 직접 사용한다.

## 작업 원칙

- 강의 내용의 정확성과 공개 범위는 프로젝트 루트의 `AGENTS.md`를 따른다.
- 사용자가 준 최종 대본은 재작성 요청이 없는 한 내용과 순서를 보존한다.
- 기본 화자는 `Sohee`, 언어는 `Korean`, 장치는 Apple Silicon에서 `MPS`다.
- 긴 대본은 생성기가 문장 단위로 나누고, 완료된 WAV 청크를 캐시하여 중단 후 재개한다.
- 모델 가중치는 로컬 캐시를 먼저 사용한다. 캐시에 없을 때만 사용자의 요청 범위 안에서
  `--allow-download`로 공개 가중치를 받는다. 대본이나 음성을 외부 서비스로 전송하지 않는다.
- 결과물을 공개하거나 Git에 추가하기 전에는 모델 라이선스와 프로젝트의 음성·바이너리
  공개 규칙을 확인하고, 합성 음성임을 오해 없게 표시한다.

## 실행

프로젝트 루트에서 입력 방식 하나를 선택한다.

```bash
python3 .agents/skills/qwen3-tts-korean-lecture/scripts/generate_qwen3_tts.py \
  --file /absolute/path/lecture.txt \
  --output output/qwen3_tts_audio/lecture.mp3
```

`--text`, `--file`, `--stdin`을 지원한다. 기본 런타임 Python은
`/Users/kimmireu/.cache/ai-content/qwen3tts-venv/bin/python`이며, 다른 환경은
`QWEN3_TTS_PYTHON` 또는 `--runtime-python`으로 지정한다. 기본 모델을 바꿀 때는
`QWEN3_TTS_MODEL` 또는 `--model`을 사용한다.

Apple Silicon에서는 생성기가 SDPA를 사용하므로 `flash-attn` 미설치 경고는 비차단이다.
로컬 SoX의 라이브러리 경고가 표시되더라도 이 생성 경로는 FFmpeg로 병합하므로 출력 검증이
통과하면 SoX 경고만으로 실패로 판단하지 않는다.

장문이나 Part별 구간 파일이 필요할 때만
[references/procurement-part-workflow.md](references/procurement-part-workflow.md)를 읽는다.

## 결과 전달

- 생성된 음성은 Codex에서 재생할 수 있도록 절대 경로로 제공한다.
- 실제 모델, 화자, 길이와 검증 결과를 함께 알린다.
- 실패한 청크, 생략된 구간, 생성 상한 도달을 숨기지 않는다.
