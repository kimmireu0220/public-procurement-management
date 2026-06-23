#!/usr/bin/env python3
"""4과목 agent_extract에 선택적 암기팁(> 💡 암기팁:)을 추가합니다."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from config import AGENT_EXTRACT_DIR, SUBJECT_CATALOG  # noqa: E402

ANSWER_HEADING_RE = re.compile(r"^#{1,3}\s+.*정답")
TIP_RE = re.compile(r"^>\s*💡\s*암기팁:")
SOURCE_RE = re.compile(r"^<!--\s*source:")
QUESTION_RE = re.compile(r"^\d+\.\s+")

# (키워드 정규식, 팁) — 먼저 매칭된 규칙만 적용
TIP_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"나라장터|G2B|전자조달"), "나라장터(G2B)는 공공조달의 전자입찰·계약 허브로, 참가자격 등록·공고·개찰까지 한곳에서 처리한다."),
    (re.compile(r"부정당업자"), "부정당업자는 입찰참가자격 제한(최대 2년) 대상이다. 입찰 전 나라장터에서 제재 여부를 반드시 확인한다."),
    (re.compile(r"직접생산확인"), "직접생산확인은 중소기업자 간 경쟁제품 물품제조 입찰의 핵심이다. 공고일 기준 유효·세부품명 일치가 실무 체크포인트다."),
    (re.compile(r"중소기업자\s*간\s*경쟁"), "중소기업자 간 경쟁제품은 세부품명 단위로 판단한다. 직접생산확인증명서가 기본 요건이다."),
    (re.compile(r"국가계약법"), "국가기관 발주 → 「국가계약법」·시행령·시행규칙이 기본 근거이다."),
    (re.compile(r"지방계약법"), "지방자치단체 발주 → 「지방계약법」·시행령·시행규칙이 기본 근거이다."),
    (re.compile(r"전기공사"), "전기공사는 「전기공사업법」에 따른 전기공사업 등록이 별도로 필요하다(건축공사업과 구분)."),
    (re.compile(r"경비업|경비용역"), "경비용역은 「경비업법」 등록이 필수다. 사업자등록 업종만으로는 갈음할 수 없다."),
    (re.compile(r"공동수급"), "공동수급은 분담이행·공동이행 방식이 있다. 각 구성원의 업종·자격을 합산해 요건 충족 여부를 본다."),
    (re.compile(r"입찰보증금"), "입찰보증금 미제출·부적격 제출은 입찰무효 사유가 될 수 있다."),
    (re.compile(r"납세증명"), "납세증명서는 보통 낙찰예정자 통보 후 제출한다. 미제출 시 낙찰 취소·계약 불성립 가능."),
    (re.compile(r"발주계획|조달계획"), "발주계획(조달계획)은 사전에 공개되어 시장 참여 전략 수립에 활용한다."),
    (re.compile(r"조달데이터허브"), "조달데이터허브는 나라장터 계약·개찰 데이터를 분석해 시장 규모·낙찰률 등을 파악하는 도구다."),
    (re.compile(r"종합쇼핑몰|MAS"), "MAS(다수공급자계약) 체결 후 종합쇼핑몰 등록으로 반복 수요에 대응할 수 있다."),
    (re.compile(r"평균\s*낙찰률|낙찰률"), "평균 낙찰률이 원가율에 근접하면 가격 경쟁이 치열하다. 입찰 참여 전 손익 분석에 활용한다."),
    (re.compile(r"예정가격"), "예정가격은 낙찰자 결정의 기준가다. 거래실례가격·원가계산 등 방식이 계약 유형·금액에 따라 달라진다."),
    (re.compile(r"이윤율"), "원가계산 시 이윤율 상한: 제조·공사·용역 각각 규정이 다르다. 시험에 수치가 자주 나온다."),
    (re.compile(r"하도급"), "하도급은 「하도급거래 공정화에 관한 법률」로 대금·서류·부당감액 등을 규율한다."),
    (re.compile(r"검수|검사"), "물품은 검수, 공사는 검사, 용역은 성과 확인 등 계약 유형별 검수·검사 용어가 다르다."),
    (re.compile(r"계약\s*변경|설계변경"), "계약 변경은 추정가격 10%·15% 등 한도와 협의 절차가 법령·계약유형별로 정해져 있다."),
    (re.compile(r"대금지급|선금|기성"), "선금·기성금·준공금 지급 비율과 시기는 계약 유형·금액에 따라 달라진다."),
    (re.compile(r"손해배상|지체상금"), "지체상금은 계약 이행 지연에 대한 손해배상의 일종으로, 계약서에 명시된 요율·한도를 따른다."),
    (re.compile(r"물품|공사|용역"), "계약 유형(물품·공사·용역)에 따라 적용 법령·면허·검수 방식이 달라진다. 입찰 전 최우선 판단 사항이다."),
    (re.compile(r"수의계약"), "수의계약은 경쟁입찰 예외로, 법령상 요건·절차를 충족해야 한다."),
    (re.compile(r"협상에\s*의한"), "협상에 의한 계약은 기술·가격 협상 절차가 있으며, 제출서류·평가 기준이 일반경쟁과 다르다."),
    (re.compile(r"적격심사"), "적격심사는 가격 입찰 후 낙찰자 결정을 위한 자격·능력 심사 제도다."),
    (re.compile(r"PQ|사전심사"), "PQ(사전심사)는 입찰 전 업체 역량을 심사해 참가 자격을 부여하는 제도다."),
    (re.compile(r"우선구매|여성기업|장애인기업|사회적기업"), "우선구매 제도(여성·장애인·사회적기업 등)는 가점·수의계약 등 입찰 전략에 활용할 수 있다."),
    (re.compile(r"세부품명|세부기준"), "세부품명(세부기준)은 물품 규격 단위다. 중소기업자 간 경쟁·직접생산확인과 직결된다."),
    (re.compile(r"업종"), "공사·용역은 등록 업종이 참가자격의 핵심이다. 물품은 직접생산확인이 더 중요한 경우가 많다."),
    (re.compile(r"면허"), "설치공사 포함 물품은 공사계약으로 볼 여지가 있어 면허(업종) 검토가 필요하다."),
    (re.compile(r"원가율|원가계산"), "원가율 ≥ 평균 낙찰률이면 적자 위험이 크다. 수요정보 분석의 핵심 비교 지표다."),
    (re.compile(r"기성검사|준공검사"), "공사 대금은 기성검사·준공검사 결과를 근거로 기성금·준공금이 지급된다."),
    (re.compile(r"청렴계약|이해충돌"), "청렴계약·이해충돌 방지는 공공조달 실무의 필수 준수 사항이다."),
    (re.compile(r"전자입찰"), "전자입찰은 나라장터를 통하며, 제출 시각·서류 형식 미준수 시 무효가 될 수 있다."),
    (re.compile(r"가격제안서|기술제안서"), "협상·제한경쟁 등에서는 기술제안서·가격제안서 제출 시한·형식 준수가 입찰 효력에 직결된다."),
    (re.compile(r"개찰|낙찰"), "개찰은 전자조달시스템에서 진행되며, 낙찰자 결정은 예정가격 대비 입찰가격·평가점수 등 규정에 따른다."),
    (re.compile(r"제한경쟁|지명경쟁"), "제한·지명경쟁은 참가자격을 사전에 제한한다. 자격요건 확보가 가격경쟁만큼 중요하다."),
    (re.compile(r"일반경쟁"), "일반경쟁입찰은 공공조달의 기본 방식이다. 자격만 갖추면 누구나 참여 가능하다."),
    (re.compile(r"계약보증금|이행보증"), "계약보증금·이행보증은 계약 이행·하자담보를 담보한다. 면제·감면 요건은 금액·계약 유형별로 다르다."),
    (re.compile(r"하자담보|하자보수"), "하자담보책임기간은 공사·물품별로 정해져 있다. 기간 내 하자 발생 시 무상 보수 의무가 있다."),
    (re.compile(r"검수|검사|인수"), "물품=검수, 공사=검사, 용역=성과확인. 인수·검수 완료 전 대금 지급에 유의한다."),
    (re.compile(r"분쟁|이의신청|심판"), "이의신청·심판청구는 법정 기한 내에 해야 한다. 기한 도과 시 구제받기 어렵다."),
    (re.compile(r"조달사업법|조달청"), "「조달사업법」은 조달청 조달사업의 법적 근거이며, 표준계약·조달정책의 기준이 된다."),
    (re.compile(r"추정가격|고시금액"), "추정가격은 부가세 제외, 고시금액은 계약방법·국제입찰 적용 기준으로 쓰인다."),
    (re.compile(r"노무비|경비|제경비"), "원가계산은 재료비·노무비·경비·일반관리비·이윤 순으로 구성된다. 노임단가는 고시 기준을 따른다."),
    (re.compile(r"공동계약|분담이행|공동이행"), "공동이행=연대책임, 분담이행=각자 부담분만 책임. 입찰공고의 이행방식을 확인한다."),
    (re.compile(r"발주기관|지방자치단체|국가기관"), "발주기관이 국가기관인지 지방자치단체인지에 따라 적용법(국가·지방계약법)이 달라진다."),
    (re.compile(r"설명회|사전규격"), "사전규격·설명회 참여는 입찰 전 요구사항·평가기준을 파악하는 실무 필수 절차다."),
    (re.compile(r"가격\s*협상|협상"), "협상계약은 기술·가격 협상 후 최종 제안가를 받는다. 단순노무용역 등 적용 제한이 있다."),
    (re.compile(r"물가변동|물가\s*연동"), "물가변동 조정은 계약 체결 후 물가 상승·하락에 따라 계약금액을 조정하는 제도다."),
    (re.compile(r"전자계약|전자서명"), "전자계약은 나라장터에서 체결·보관된다. 전자서명·인증서 유효성을 확인한다."),
    (re.compile(r"참여업체|경쟁\s*강도"), "참여업체 수가 많고 낙찰률이 낮을수록 가격 경쟁이 치열하다."),
    (re.compile(r"손익|적자|수익"), "입찰 전 (예상 낙찰가−원가) 손익 분석 없이 참여하면 적자 수주 위험이 있다."),
    (re.compile(r"기술평가|종합평가"), "종합평가·협상계약은 기술·가격 비중을 확인한다. 기술점수 확보 전략이 필요하다."),
    (re.compile(r"청구|대금"), "대금 청구는 검수·검사 완료·세금계산서 등 요건을 갖춰야 한다."),
    (re.compile(r"해제|해지"), "해제=소급 소멸, 해지=장래 소멸. 공공계약에서 채무불이행·계약위반 시 주요 제재 수단이다."),
]

# 섹션 제목 기반 보조 팁 (키워드 미매칭 시)
SECTION_TIPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"입찰참가|참가\s*준비"), "입찰 참가 전 체크순서: 발주기관→계약유형→적용법령→자격요건→서류·보증금."),
    (re.compile(r"수요정보|시장\s*분석|공급계획"), "수요정보 분석 3요소: 시장규모·성장성·경쟁강도(낙찰률·참여업체 수)."),
    (re.compile(r"원가계산|가격\s*산정"), "원가계산은 예정가격·입찰가격 산정의 기초다. 이윤율 상한·노임단가 고시를 숙지한다."),
    (re.compile(r"계약\s*체결|계약\s*이행"), "계약 체결=서명·날인 시 성립. 이행 단계별 검수·대금·하자담보를 순서대로 관리한다."),
    (re.compile(r"하도급"), "하도급은 법정 서류·대금 지급기한·부당감액 금지를 반드시 준수한다."),
    (re.compile(r"검수|검사|준공"), "검수·검사·준공은 대금 지급의 전제다. 하자 발견 시 하자담보책임을 확인한다."),
    (re.compile(r"분쟁|이의|심판"), "분쟁 대응: 이의신청(행정기관)→심판청구→소송 순으로 기한을 엄수한다."),
    (re.compile(r"Check\s*Q&A|핵심\s*최종"), "Check·최종점검 문항은 시험 빈출 암기 포인트다. 법령명·기한·수치를 정확히 외운다."),
    (re.compile(r"서술형"), "서술형은 사례→법적 쟁점→근거 법령→결론 순으로 답안을 구성한다."),
]


def pick_tip(block_text: str, section: str = "") -> str | None:
    for pattern, tip in TIP_RULES:
        if pattern.search(block_text):
            return tip
    combined = f"{section}\n{block_text}"
    for pattern, tip in SECTION_TIPS:
        if pattern.search(combined):
            return tip
    return None


def process_text(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    out: list[str] = []
    in_answers = False
    section = ""
    added = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if ANSWER_HEADING_RE.match(line.strip()):
            in_answers = True
            out.append(line)
            i += 1
            continue
        if line.startswith("## "):
            section = line
        if in_answers or not QUESTION_RE.match(line.strip()):
            out.append(line)
            i += 1
            continue
        block = [line]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if QUESTION_RE.match(nxt.strip()) or nxt.strip().startswith("##"):
                break
            if SOURCE_RE.match(nxt.strip()):
                block.append(nxt)
                j += 1
                break
            block.append(nxt)
            j += 1
        has_tip = any(TIP_RE.match(b.strip()) for b in block)
        source_idx = next((k for k, b in enumerate(block) if SOURCE_RE.match(b.strip())), None)
        if not has_tip and source_idx is not None:
            tip = pick_tip("\n".join(block), section)
            if tip:
                block.insert(source_idx, f"> 💡 암기팁: {tip}")
                added += 1
        out.extend(block)
        i = j
    return "\n".join(out).rstrip() + "\n", added


def main() -> None:
    parser = argparse.ArgumentParser(description="4과목 문항에 암기팁을 추가합니다.")
    parser.add_argument("--subject", default="4", choices=sorted(SUBJECT_CATALOG))
    parser.add_argument("--part", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slug = str(SUBJECT_CATALOG[args.subject]["slug"])
    base = AGENT_EXTRACT_DIR / slug
    if args.subject != "4":
        print("암기팁은 4과목 전용입니다.", file=sys.stderr)
        sys.exit(1)
    parts = [base / f"part{args.part}.md"] if args.part else sorted(base.glob("part*.md"))
    total = 0
    for path in parts:
        if not path.is_file():
            continue
        new_text, n = process_text(path.read_text(encoding="utf-8"))
        total += n
        if n and not args.dry_run:
            path.write_text(new_text, encoding="utf-8")
        print(f"{path.name}: {n}개 암기팁 추가")
    print(f"합계 {total}개{' (dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
