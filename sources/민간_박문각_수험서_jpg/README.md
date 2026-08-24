# 민간 수험서 스캔 보관 위치

이 디렉터리의 이미지 원본은 개인적으로 적법하게 확보한 경우에만 로컬에 두며,
Git과 GitHub Pages에는 올리지 않는다. `.gitignore`가 이 안내 파일을 제외한 모든
이미지를 차단한다. `inventory.json`에는 재현 가능한 출처 확인을 위해 파일의 상대
경로·크기·SHA-256만 기록하며 이미지 내용은 포함하지 않는다.

파일 구조는 필요에 따라 바꿀 수 있다. 경로를 바꾸면 문제은행의 Markdown과 `source`
표시처럼 이 로컬 페이지를 가리키는 내부 참조도 함께 갱신한다.
민간 교재의 복제·배포 허락을 뜻하지 않는다.

```bash
python3 tools/private_source_inventory.py --write
python3 tools/private_source_inventory.py
```
