from __future__ import annotations

import html
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import (  # noqa: E402
    AGENT_EXTRACT_DIR,
    BUILD_REPORT,
    CHAPTERS_CLEAN_DIR,
    PROBLEM_BOOK_FINAL_DIR,
    PROBLEM_BOOK_MD,
)

SOURCE_DIR = AGENT_EXTRACT_DIR
FINAL_DIR = PROBLEM_BOOK_FINAL_DIR
CHAPTERS_DIR = CHAPTERS_CLEAN_DIR

ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답")
QUESTION_RE = re.compile(r"^\s*\d+\.\s+\S")
SOURCE_RE = re.compile(r"<!--\s*source:\s*([^>]+?)\s*-->")


def strip_answer_section(text: str) -> tuple[str, int | None]:
    lines = text.splitlines()
    cut_at = None
    for i, line in enumerate(lines):
        if ANSWER_HEADING_RE.match(line.strip()):
            cut_at = i
            break
    if cut_at is None:
        return text.rstrip() + "\n", None
    return "\n".join(lines[:cut_at]).rstrip() + "\n", cut_at + 1


def demote_headings(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.startswith("### "):
            out.append("#### " + line[4:])
        elif line.startswith("## "):
            out.append("### " + line[3:])
        elif line.startswith("# "):
            out.append("## " + line[2:])
        else:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"


def add_source_note_before(text: str, heading: str, note: str) -> str:
    marker = f"\n{heading}"
    if note in text or marker not in text:
        return text
    return text.replace(marker, f"\n{note}\n{marker}", 1)


def replace_section(text: str, start: str, end: str, replacement: str) -> str:
    start_at = text.find(start)
    if start_at == -1:
        return text
    end_at = text.find(end, start_at + len(start))
    if end_at == -1:
        return text
    return text[:start_at] + replacement.rstrip() + "\n\n" + text[end_at:]


def augment_sources(chapter: int, text: str) -> str:
    if chapter == 1:
        text = replace_section(
            text,
            "### Chapter 01 공공조달의 정의 및 목적 — Check Q&A",
            "### Chapter 01 단원별 출제예상문제",
            """### Chapter 01 공공조달의 정의 및 목적 — Check Q&A

1. 공공조달의 가장 기본적인 정의로 옳은 것은?
   ① 민간기업이 이윤을 목적으로 물품을 구매하는 활동
   ② 공공부문이 필요한 물품·용역·공사를 구매하는 절차
   ③ 국제기구 간 무역 협정을 체결하는 활동
   ④ 공기업이 자체 생산을 통해 물자를 조달하는 과정
<!-- source: Chapter 1/page_0002.jpg -->

2. 공공조달이 민간구매와 구별되는 가장 핵심적인 특징은?
   ① 거래 절차의 단순성
   ② 계약 자유의 원칙 적용
   ③ 공공서비스 제공 목적
   ④ 신속한 의사결정
<!-- source: Chapter 1/page_0003.jpg -->

3. 공공조달에서 투명성이 요구되는 이유로 가장 적절한 것은?
   ① 계약 기간 단축
   ② 시장의 독점 방지
   ③ 공급자에게 편의 제공
   ④ 국민에 대한 설명 책임
<!-- source: Chapter 1/page_0003.jpg -->

4. 공공조달이 역사적으로 가장 먼저 수행된 주요 목적은?
   ① 중소기업 보호
   ② 사회적 가치 실현
   ③ 산업 경쟁력 강화
   ④ 국가 운영에 필요한 물자의 확보
<!-- source: Chapter 1/page_0004.jpg -->

5. 다음 중 조선시대 공공조달 제도의 변화에 대한 설명으로 옳은 것은?
   ① 조선 초기에는 시전상인이 특허상인의 역할을 했고, 대동법 시행 이후에는 공인이 그 역할을 담당하였다.
   ② 조선 후기에는 일본 상인이 직접 조달을 담당하였다.
   ③ 삼국시대에는 공계인이 등장하여 조달을 담당하였다.
   ④ 조선시대 전 기간 동안 왕실이 직접 모든 물품을 조달하였다.
<!-- source: Chapter 1/page_0006.jpg -->

6. 공공조달의 중요성에 대한 설명으로 가장 기본적인 것은?
   ① 행정 편의성 증대
   ② 국가 재정 집행의 핵심 수단
   ③ 국제무역 확대
   ④ 민간시장 경쟁
<!-- source: Chapter 1/page_0007.jpg -->

7. 공공조달의 중요성이 최근 더욱 강조되는 배경으로 옳은 것은?
   ① 조달 규모 축소
   ② 정부 역할 약화
   ③ 정책 목표의 복합화·고도화
   ④ 민간시장 완전 경쟁
<!-- source: Chapter 1/page_0009.jpg -->

8. 공공조달의 가장 기본적인 목적으로 옳은 것은?
   ① 민간기업 축소
   ② 공공서비스 제공에 필요한 자원의 확보
   ③ 국제무역 확대
   ④ 조세 부담 경감
<!-- source: Chapter 1/page_0009.jpg -->

9. 공공조달 목적 중 '효율성(Value for Money)'의 의미로 가장 적절한 것은?
   ① 최저가로 구매하는 것
   ② 단기 예산 집행을 우선하는 것
   ③ 비용 대비 성과와 가치를 극대화하는 것
   ④ 공급자 이윤을 최소화하는 것
<!-- source: Chapter 1/page_0009.jpg -->

10. 공공조달이 정책 목표 달성 수단으로 활용될 때의 특징은?
    ① 가격만을 기준으로 한다.
    ② 단기 집행 성과만 중시한다.
    ③ 조달 기준에 정책 요소를 반영한다.
    ④ 민간 시장을 대체한다.
<!-- source: Chapter 1/page_0010.jpg -->

11. 공공조달 대상에 '용역'이 포함된다는 의미로 가장 적절한 것은?
    ① 유형 자산만 포함한다.
    ② 인적·지식 서비스도 포함한다.
    ③ 금융 거래를 의미한다.
    ④ 조세 행위를 포함한다.
<!-- source: Chapter 1/page_0011.jpg -->

12. 다음 중 공공조달 범위에 대한 올바른 이해는?
    ① 계약 이후 단계는 제외된다.
    ② 예산 편성은 항상 제외된다.
    ③ 공공서비스 실행 전 과정이다.
    ④ 민간시장과 무관하다.
<!-- source: Chapter 1/page_0012.jpg -->""",
        )

    if chapter == 3:
        text = replace_section(
            text,
            "### Chapter 01 전자조달시스템 개요 — Check Q&A",
            "### Chapter 01 단원별 출제예상문제",
            """### Chapter 01 전자조달시스템 개요 — Check Q&A

1. 전자조달시스템 도입의 주요 목적과 가장 거리가 먼 것은?
   ① 비용 절감
   ② 업무 효율성 향상
   ③ 조달 과정의 가시성 제고
   ④ 공급자 이윤 극대화
<!-- source: Chapter 3/page_0002.jpg -->

2. 전자적 소싱(e-Sourcing)에 대한 설명으로 가장 적절한 것은?
   ① 계약 이행 이후의 구매 집행을 지원한다.
   ② 납품 및 대금 지급을 전자적으로 처리한다.
   ③ 공급업체 선정과 경쟁 과정을 전자적으로 지원한다.
   ④ 회계 및 결산 기능을 수행한다.
<!-- source: Chapter 3/page_0003.jpg -->

3. 고도의 기술적 전문성과 품질 검증이 핵심인 지출 유형은?
   ① 인수 지출
   ② 레버리지 지출
   ③ 전략적 지출
   ④ 기술적 지출
<!-- source: Chapter 3/page_0005.jpg -->

4. 조달 대상의 전략적 중요도와 공급 위험이 모두 낮은 지출 유형은?
   ① 전략적 지출
   ② 기술적 지출
   ③ 레버리지 지출
   ④ 인수 지출
<!-- source: Chapter 3/page_0005.jpg -->

5. 다음 중 전통적 공공조달 프로세스를 지원하는 전자시스템의 도입 효과로 가장 적절하지 않은 것은?
   ① 조달 절차의 법적 구조 유지
   ② 행정 처리 속도 향상
   ③ 조달 방식의 제도적 전환
   ④ 기록 관리 및 책임성 강화
<!-- source: Chapter 3/page_0006.jpg -->

6. 전통적 공공조달 프로세스를 지원하는 전자시스템의 특징으로 가장 적절한 것은?
   ① 기존 조달 절차를 인터넷 플랫폼으로 전면 대체한다.
   ② 공공조달 법·제도를 변경하여 운영한다.
   ③ 기존 조달 절차를 유지하면서 전자적으로 지원한다.
   ④ 민간 B2B 거래 방식을 그대로 도입한다.
<!-- source: Chapter 3/page_0007.jpg -->

7. 전자조달시스템의 표준 기능이 필요한 가장 근본적인 이유는?
   ① 조달 속도 향상
   ② IT 비용 절감
   ③ 공공조달 운영의 표준화와 책임성 확보
   ④ 민간 플랫폼과의 경쟁
<!-- source: Chapter 3/page_0008.jpg -->

8. 전자역매(E-Reverse Auction)는 어떤 경우에 적합한가?
   ① 기술적 평가가 중요한 복잡한 입찰
   ② 가격 외 고려사항이 중요한 입찰
   ③ 상용화·표준화된 범용적 상품 조달
   ④ 고가의 맞춤형 장비 조달
<!-- source: Chapter 3/page_0009.jpg -->

9. 전자조달시스템 도입으로 기대되는 행정 효율성 성과로 가장 적절한 것은?
   ① 계약 절차 복잡화
   ② 문서 관리 비용 증가
   ③ 조달 처리 시간 단축
   ④ 공급자 수 감소
<!-- source: Chapter 3/page_0011.jpg -->""",
        )
        text = replace_section(
            text,
            "### Chapter 02 국가종합전자조달시스템(나라장터) — Check Q&A",
            "### Chapter 02 단원별 출제예상문제",
            """### Chapter 02 국가종합전자조달시스템(나라장터) — Check Q&A

1. 나라장터를 통해 조달기업이 처리할 수 없는 업무는?
   ① 입찰서 제출
   ② 계약 체결
   ③ 검사검수
   ④ 대금 지급 요청
<!-- source: Chapter 3/page_0018.jpg -->

2. 나라장터가 국제적으로 우수 사례로 인정받은 이유로 가장 적절한 것은?
   ① 국내 조달시장 보호 기능
   ② 공공조달의 민영화
   ③ 투명성·표준화·통합 운영 성과
   ④ 특정 국가에만 적용 가능한 시스템 구조
<!-- source: Chapter 3/page_0019.jpg -->

3. 전자조달시스템 이용자에 대한 설명으로 가장 적절한 것은?
   ① 전자조달시스템 운영기관만을 의미한다.
   ② 조달기업만 시스템을 이용할 수 있다.
   ③ 공공조달 전 과정에 참여하거나 이를 지원하는 주체를 포함한다.
   ④ 조달기관은 이용자에 포함되지 않는다.
<!-- source: Chapter 3/page_0019.jpg -->

4. 발주 절차에 대한 설명으로 가장 적절한 것은?
   ① 계약 체결 이후 단계만을 의미한다.
   ② 조달 필요 발생부터 계약 체결까지의 공식적 과정이다.
   ③ 전자조달시스템과 무관하게 운영된다.
   ④ 조달기업만 수행하는 절차이다.
<!-- source: Chapter 3/page_0020.jpg -->

5. 중앙조달의 주요 장점으로 보기 어려운 것은?
   ① 규모의 경제 실현
   ② 조달 전문성 축적
   ③ 수요기관의 행정 부담 증가
   ④ 표준화된 절차 운영
<!-- source: Chapter 3/page_0021.jpg -->

6. 전자조달에서 지불 단계가 중요한 이유는?
   ① 경쟁성을 확보할 수 있기 때문
   ② 조달 절차의 최종 단계이기 때문
   ③ 정책 수립 단계이기 때문
   ④ 협상 단계이기 때문
<!-- source: Chapter 3/page_0023.jpg -->

7. 전자조달시스템에서 입찰공고에 포함되는 내용이 아닌 것은?
   ① 참가자격
   ② 평가 기준
   ③ 예정가격
   ④ 입찰 일정
<!-- source: Chapter 3/page_0024.jpg -->""",
        )
        text = replace_section(
            text,
            "### Chapter 03 나라장터 연계 계약관리 지원시스템 — Check Q&A",
            "### Chapter 03 단원별 출제예상문제",
            """### Chapter 03 나라장터 연계 계약관리 지원시스템 — Check Q&A

1. 다수공급자계약(MAS)의 가장 큰 특징으로 옳은 것은?
   ① 단일 공급자와의 장기계약
   ② 2단계 경쟁 구조
   ③ 수의계약 전용 방식
   ④ 협상에 의한 계약
<!-- source: Chapter 3/page_0034.jpg -->

2. 다수공급자계약의 2단계 경쟁 주체는 누구인가?
   ① 조달청
   ② 감사기관
   ③ 수요기관
   ④ 계약업체
<!-- source: Chapter 3/page_0034.jpg -->

3. 수요기관이 종합쇼핑몰에서 계약업체를 선택할 때 고려 요소로 가장 적절하지 않은 것은?
   ① 가격
   ② 납기
   ③ 계약 이행 실적
   ④ 조달청 내부 인사 평가
<!-- source: Chapter 3/page_0035.jpg -->

4. 혁신장터의 주된 목적은 무엇인가?
   ① 최저가 구매 확대
   ② 대기업 제품 우선 구매
   ③ 혁신제품의 공공 판로 지원
   ④ 수의계약 축소
<!-- source: Chapter 3/page_0035.jpg -->

5. 혁신제품 시범구매의 목적은?
   ① 단기 수익 창출
   ② 가격 경쟁 강화
   ③ 기술 검증 및 실증
   ④ 계약 해지 용이화
<!-- source: Chapter 3/page_0036.jpg -->

6. 벤처나라 등록 대상 기업으로 옳은 것은?
   ① 모든 대기업
   ② 외국계 기업
   ③ 벤처기업 및 창업기업
   ④ 공기업
<!-- source: Chapter 3/page_0037.jpg -->

7. 디지털서비스몰의 조달 대상에 해당하지 않는 것은?
   ① 클라우드 서비스
   ② 상용 소프트웨어
   ③ ICT 기반 서비스
   ④ 건설 공사
<!-- source: Chapter 3/page_0038.jpg -->

8. 디지털서비스몰 계약의 특징으로 옳은 것은?
   ① 장기·고정 계약만 허용
   ② 이용 중심 계약 구조
   ③ 물품 납품 중심
   ④ 최저가 입찰 필수
<!-- source: Chapter 3/page_0039.jpg -->

9. 이음장터에서 거래 가능한 용역(서비스)의 최대 거래 금액은 부가가치세를 포함하여 얼마인가?
   ① 2,000만원
   ② 5,500만원
   ③ 2,200만원
   ④ 3,000만원
<!-- source: Chapter 3/page_0039.jpg -->""",
        )

    if chapter == 5:
        text = replace_section(
            text,
            "### Chapter 02 중소기업지원 조달 — Check Q&A",
            "### Chapter 02 단원별 출제예상문제",
            """### Chapter 02 중소기업지원 조달 — Check Q&A

1. 중소기업의 공공조달시장 참여 확대를 위해 OECD 및 EU 회원국들이 공통적으로 추진하는 원칙이 아닌 것은?
   ① 효과적인 경쟁 원칙 실행
   ② 대기업 우선 낙찰 보장
   ③ 평등한 대우 보장
   ④ 개방적 접근성 제공
<!-- source: Chapter 5/page_0009.jpg -->

2. 우리나라 중소기업의 기업 수 비중으로 가장 적절한 것은?
   ① 약 70%
   ② 약 85%
   ③ 약 95%
   ④ 약 99.9%
<!-- source: Chapter 5/page_0009.jpg -->

3. 중소기업 공공구매제도의 법적 근거로 가장 핵심적인 법률은?
   ① 국가계약법
   ② 지방계약법
   ③ 판로지원법
   ④ 조달사업법

4. 중소기업자 간 경쟁제도의 기본 목적은?
   ① 대기업 참여 확대
   ② 조달 절차 간소화
   ③ 중소기업 판로 확대
   ④ 계약 기간 단축

5. 직접생산확인제도의 목적은?
   ① 가격 담합 방지
   ② 중소기업의 위장 참여 방지
   ③ 계약 기간 단축
   ④ 품질 인증 대체

6. 조합추천 소액수의계약의 특징으로 옳은 것은?
   ① 대기업 추천 가능
   ② 일정 금액 이하 수의계약
   ③ 공개경쟁 필수
   ④ 성능인증 필수

7. 기술개발제품 공공기관 실증지원 사업의 목적은?
   ① 기술 표준화
   ② 시제품 상용화 검증
   ③ 가격 경쟁 유도
   ④ 수의계약 확대

8. 성능인증제도의 주요 목적은?
   ① 가격 인증
   ② 환경 인증
   ③ 기술 성능 검증
   ④ 수출 지원
<!-- source: Chapter 5/page_0010.jpg ~ page_0014.jpg -->""",
        )

    if chapter != 6:
        return text

    text = replace_section(
        text,
        "### Chapter 03 Check Q&A",
        "### Chapter 03 단원별 출제예상문제",
        """### Chapter 03 Check Q&A

1. 「조달사업법」의 제정 목적으로 가장 옳은 것은?
   ① 국가재정 절감
   ② 조달사업의 공정성과 효율성 확보
   ③ 중소기업 보호만을 목적
   ④ 지방계약 통합 운영
<!-- source: Chapter 6/page_0032.jpg -->

2. 조달정책심의위원회의 심의사항으로 옳지 않은 것은?
   ① 공공조달의 중장기 정책 수립
   ② 공공수요 발굴 및 구매 대상 선정
   ③ 개별 계약의 낙찰자 결정
   ④ 공공조달의 성과관리 평가
<!-- source: Chapter 6/page_0032.jpg -->

3. 조달데이터허브의 운영 목적은?
   ① 계약 비공개
   ② 조달정보 독점
   ③ 조달데이터 개방을 통한 투명성 확보
   ④ 조달기업 관리
<!-- source: Chapter 6/page_0033.jpg -->

4. 조달청과 수요기관 간 협의가 이루어지지 않을 경우 옳은 것은?
   ① 계약 불가
   ② 조달청이 일방적으로 결정
   ③ 수요기관이 직접 계약 가능
   ④ 재정경제부 승인 필요
<!-- source: Chapter 6/page_0033.jpg -->

5. 다수공급자계약(MAS)의 계약상대자 수 요건은?
   ① 1인
   ② 2인 이상
   ③ 3인 이상
   ④ 제한 없음
<!-- source: Chapter 6/page_0034.jpg -->

6. 다음 중 대지급 대상 계약이 아닌 것은?
   ① 제3자 단가계약
   ② 다수공급자계약
   ③ 소액 수의계약
   ④ 천재지변 복구공사
<!-- source: Chapter 6/page_0035.jpg -->

7. 포상금 지급의 목적으로 옳은 것은?
   ① 예산 집행 확대
   ② 조달기업 보호
   ③ 내부·외부 감시 촉진
   ④ 계약 신속화
<!-- source: Chapter 6/page_0036.jpg -->

8. 거래정지 처분 기간의 최대 범위는?
   ① 6개월
   ② 1년
   ③ 2년
   ④ 5년
<!-- source: Chapter 6/page_0036.jpg -->""",
    )
    text = replace_section(
        text,
        "### Chapter 05 Check Q&A",
        "### Chapter 05 단원별 출제예상문제",
        """### Chapter 05 Check Q&A

1. 공기업과 준정부기관은 기본적으로 어떤 법령을 적용받는가?
   ① 「민법」
   ② 「상법」
   ③ 국가계약법령
   ④ 지방계약법령
<!-- source: Chapter 6/page_0051.jpg -->

2. 「계약사무규칙」 제7조에 따라 계약사무 위탁이 가능한 경우는?
   ① 기관 소속 직원에게 위임
   ② 다른 기관장에게 위탁
   ③ 국가·지자체 기관에 위탁
   ④ 모두 해당
<!-- source: Chapter 6/page_0052.jpg -->

3. 중소기업자 간 경쟁제품 구매 예외 사유가 아닌 것은?
   ① 긴급 구매 필요
   ② 디자인 공모 반영
   ③ 기관 고유사업 지원
   ④ 일반 소비재 구매
<!-- source: Chapter 6/page_0052.jpg -->

4. 공기업·준정부기관이 수의계약을 체결할 수 있는 경우가 아닌 것은?
   ① 국가·지자체와 계약
   ② 자회사와 계약
   ③ 일반 민간기업과 계약
   ④ 특정기술 보호 목적 계약
<!-- source: Chapter 6/page_0053.jpg -->

5. 의견 진술 통지의 최소 기한은?
   ① 3일 전
   ② 5일 전
   ③ 7일 전
   ④ 10일 전
<!-- source: Chapter 6/page_0054.jpg -->

6. 이의신청 기한은 원인행위 발생일로부터 며칠 이내인가?
   ① 10일
   ② 15일
   ③ 20일
   ④ 30일
<!-- source: Chapter 6/page_0055.jpg -->""",
    )

    additions = [
        ("### Chapter 01 최종점검 OX 퀴즈", "<!-- source: Chapter 6/page_0013.jpg ~ page_0017.jpg -->"),
        ("### Chapter 02 최종점검 OX 퀴즈", "<!-- source: Chapter 6/page_0026.jpg ~ page_0029.jpg -->"),
        ("### Chapter 03 최종점검 OX 퀴즈", "<!-- source: Chapter 6/page_0038.jpg ~ page_0042.jpg -->"),
        ("### Chapter 04 최종점검 OX 퀴즈", "<!-- source: Chapter 6/page_0047.jpg ~ page_0049.jpg -->"),
        ("### Chapter 05 최종점검 OX 퀴즈", "<!-- source: Chapter 6/page_0056.jpg ~ page_0057.jpg -->"),
        ("### Chapter 06 최종점검 OX 퀴즈", "<!-- source: Chapter 6/page_0065.jpg -->"),
    ]
    for heading, note in additions:
        text = add_source_note_before(text, heading, note)
    return text


def make_html(markdown_text: str) -> str:
    body_lines: list[str] = []
    in_list = False
    for raw in markdown_text.splitlines():
        line = raw.rstrip()
        if not line:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("<!--"):
            continue
        if line.startswith("# "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("#### "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h4>{html.escape(line[5:])}</h4>")
        elif line.startswith("> "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif re.match(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]", line):
            if not in_list:
                body_lines.append("<ul class=\"choices\">")
                in_list = True
            body_lines.append(f"<li>{html.escape(line.strip())}</li>")
        elif re.match(r"^\s*\d+\.\s+", line):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<p class=\"question\">{html.escape(line.strip())}</p>")
        elif line == "---":
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append("<hr>")
        else:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<p>{html.escape(line.strip())}</p>")
    if in_list:
        body_lines.append("</ul>")

    return """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>공공조달의 이해 문제집</title>
<style>
@page { margin: 18mm 16mm; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  line-height: 1.55;
  color: #111;
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
}
h1 { font-size: 28px; margin: 0 0 22px; }
h2 { font-size: 22px; margin: 34px 0 12px; padding-top: 14px; border-top: 2px solid #222; }
h3 { font-size: 18px; margin: 24px 0 10px; }
h4 { font-size: 15px; margin: 18px 0 8px; }
p { margin: 6px 0; }
blockquote { color: #555; border-left: 4px solid #ddd; padding-left: 12px; margin: 8px 0 18px; }
.question { font-weight: 600; margin-top: 14px; break-inside: avoid; }
.choices { list-style: none; padding-left: 22px; margin: 4px 0 12px; break-inside: avoid; }
.choices li { margin: 2px 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 24px 0; }
@media print {
  body { max-width: none; padding: 0; }
  h2 { break-before: page; }
  h2:first-of-type { break-before: auto; }
}
</style>
</head>
<body>
""" + "\n".join(body_lines) + """
</body>
</html>
"""


def main() -> None:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    combined_parts = [
        "# 공공조달의 이해 문제집",
        "",
        "> 교재 폴더의 문제 유형(Check Q&A, 단원별 출제예상문제, 최종점검 OX 퀴즈)만 모은 학습용 합본입니다.",
        "",
    ]
    report_lines = [
        "# 문제집 생성 검토 요약",
        "",
        "| 챕터 파일 | 정답 섹션 제거 시작 줄 | 문제 수 | 출처 주석 수 |",
        "|---|---:|---:|---:|",
    ]

    for n in range(1, 8):
        source = SOURCE_DIR / f"chapter{n}.md"
        text = source.read_text(encoding="utf-8")
        stripped, cut_line = strip_answer_section(text)
        clean = demote_headings(stripped)
        clean = augment_sources(n, clean)
        clean_path = CHAPTERS_DIR / f"chapter{n}.md"
        clean_path.write_text(clean, encoding="utf-8")

        question_count = sum(1 for line in clean.splitlines() if QUESTION_RE.match(line))
        source_count = len(SOURCE_RE.findall(clean))
        cut_label = str(cut_line) if cut_line else "-"
        report_lines.append(f"| chapter{n}.md | {cut_label} | {question_count} | {source_count} |")
        combined_parts.append(clean.rstrip())
        combined_parts.append("")

    combined = "\n".join(combined_parts).rstrip() + "\n"
    md_path = FINAL_DIR / "공공조달의_이해_문제집.md"
    html_path = FINAL_DIR / "공공조달의_이해_문제집.html"
    report_path = BUILD_REPORT

    md_path.write_text(combined, encoding="utf-8")
    html_path.write_text(make_html(combined), encoding="utf-8")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(md_path)
    print(html_path)
    print(report_path)


if __name__ == "__main__":
    main()
