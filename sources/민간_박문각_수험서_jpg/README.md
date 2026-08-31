# 민간 수험서 스캔 자료

이 디렉터리의 이미지는 현재 Git 추적 대상이다. 저장소에 존재하거나 추적된다는 사실은
복제·재배포 권한의 증거가 아니므로, 새 자료를 추가하거나 외부 산출물에 사용할 때는
별도로 이용조건과 권리 상태를 확인한다.

`inventory.json`은 파일의 상대 경로·크기·SHA-256을 기록한다. 경로를 바꾸면 문제은행의
Markdown과 `source` 표시 등 내부 참조도 함께 갱신한다.

```bash
python3 tools/private_source_inventory.py --write
python3 tools/private_source_inventory.py
```
