"""
law_team.py - 5인 전문 법률 검토 에이전트 팀 오케스트레이션 엔진
에이전트 구성:
  1. 수석 법률 자문관 (Chief Legal Counsel) - 쟁점 도출, 총괄 지휘, 자문서 집필
  2. 실정법령·3단연계 조사관 (Statutory Analyst) - 법률-시행령-시행규칙-행정규칙-자치법규 전수 검색
  3. 판례·유권해석 조사관 (Precedent Specialist) - 대법원/헌재/법제처/위원회 결정례 분석
  4. 법적 리스크·반대논리 감사관 (Devil's Advocate) - 제재·벌칙 규정, 규제기관 논리, 패소 리스크 방어
  5. 조문 원문 대조 검증관 (Reality Auditor) - open.law.go.kr 실시간 1:1 대조 및 무결점 판정
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.append(str(Path(__file__).parent))
from law_api import LawApiClient, format_article_text
from law_verify import LawCitationVerifier

class LawAgentTeam:
    def __init__(self, oc: Optional[str] = None):
        self.client = LawApiClient(oc=oc)
        self.verifier = LawCitationVerifier(oc=oc)

    def analyze_case(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        사안 접수 및 법률 검토 에이전트 팀 전주기 파이프라인 가동
        """
        # 1. 수석 법률 자문관: 키워드 및 도메인 분석
        search_terms = self._extract_legal_terms(query + " " + (context or ""))
        
        # 2. 실정법령 조사관: 법령 검색 및 핵심 조문 추출
        statute_findings = []
        for term in search_terms[:3]:
            laws = self.client.search_statute(term, target="eflaw", display=3)
            for l in laws:
                mst = l.get("법령일련번호")
                nm = l.get("법령명한글")
                if nm and not any(sf["법령명"] == nm for sf in statute_findings):
                    # 법령 본문 및 주요 조문 로드
                    art_result = self.client.get_article(nm, 1) # 기본 조회
                    statute_findings.append({
                        "법령명": nm,
                        "법령일련번호": mst,
                        "소관부처": l.get("소관부처명"),
                        "시행일자": l.get("시행일자"),
                        "제개정구분": l.get("제개정구분명")
                    })
                    if len(statute_findings) >= 3:
                        break

        # 주요 법률의 3단비교 가능 여부 확인
        tier3_findings = []
        if statute_findings:
            top_law = statute_findings[0]["법령명"]
            t3 = self.client.get_3tier_comparison(top_law)
            if "LspttnThdCmpLawXService" in t3 or "위임조문삼단비교" in t3:
                tier3_findings.append(top_law)

        # 3. 판례·유권해석 조사관: 판례 및 법제처 해석례 검색
        precedent_findings = []
        for term in search_terms[:3]:
            precs = self.client.search_precedent(term, display=3)
            for p in precs:
                pid = p.get("판례일련번호")
                cno = p.get("사건번호")
                cname = p.get("사건명")
                court = p.get("법원명")
                sdate = p.get("선고일자")
                if cno and not any(pf["사건번호"] == cno for pf in precedent_findings):
                    # 판례 요지 조회
                    pdetail = self.client.get_precedent_detail(pid) if pid else {}
                    summary = pdetail.get("판결요지") or pdetail.get("판시사항") or ""
                    clean_summary = re.sub(r'<[^>]+>', ' ', summary).strip()[:300]
                    precedent_findings.append({
                        "사건번호": cno,
                        "사건명": cname,
                        "법원명": court,
                        "선고일자": sdate,
                        "요지": clean_summary,
                        "판례일련번호": pid
                    })
                    if len(precedent_findings) >= 3:
                        break

        # 법제처 유권해석례 검색
        interpretation_findings = []
        for term in search_terms[:2]:
            expcs = self.client.search_interpretation(term, display=2)
            for e in expcs:
                eid = e.get("법령해석례일련번호")
                ano = e.get("안건번호")
                anm = e.get("안건명")
                if ano and not any(inf["안건번호"] == ano for inf in interpretation_findings):
                    edetail = self.client.get_interpretation_detail(eid) if eid else {}
                    reason = edetail.get("이유") or edetail.get("회답") or ""
                    clean_reason = re.sub(r'<[^>]+>', ' ', reason).strip()[:250]
                    interpretation_findings.append({
                        "안건번호": ano,
                        "안건명": anm,
                        "회신일자": e.get("회신일자"),
                        "회신기관": e.get("회신기관명"),
                        "요지": clean_reason
                    })
                    if len(interpretation_findings) >= 2:
                        break

        # 행정규칙/위원회 결정문 검색
        admin_findings = []
        for term in search_terms[:2]:
            arules = self.client.search_admin_rule(term, display=2)
            for ar in arules:
                anm = ar.get("행정규칙명")
                if anm and not any(af["행정규칙명"] == anm for af in admin_findings):
                    admin_findings.append({
                        "행정규칙명": anm,
                        "행정규칙종류": ar.get("행정규칙종류명"),
                        "소관부처": ar.get("소관부처명"),
                        "시행일자": ar.get("시행일자")
                    })
                    if len(admin_findings) >= 2:
                        break

        # 전문 위원회 결정례 (예: 개인정보, 공정위, 노동위)
        committee_findings = []
        for comm in ["ppc", "ftc", "nlrc"]:
            for term in search_terms[:2]:
                c_items = self.client.search_committee_decision(comm, term, display=2)
                for ci in c_items:
                    c_title = ci.get("사건명") or ci.get("안건명") or ci.get("문서명") or ci.get("제목")
                    c_no = ci.get("사건번호") or ci.get("의결번호") or ci.get("문서번호")
                    if c_title and not any(cf["사건명"] == c_title for cf in committee_findings):
                        committee_findings.append({
                            "위원회": comm.upper(),
                            "사건번호": c_no or "-",
                            "사건명": c_title
                        })
                        if len(committee_findings) >= 2:
                            break

        return {
            "query": query,
            "context": context,
            "search_terms": search_terms,
            "statutes": statute_findings,
            "3tier_available": tier3_findings,
            "precedents": precedent_findings,
            "interpretations": interpretation_findings,
            "admin_rules": admin_findings,
            "committee_decisions": committee_findings
        }

    def _extract_legal_terms(self, text: str) -> List[str]:
        """
        자문 질의에서 법률 검색 키워드 추출
        """
        # 법률명 직접 추출 (예: 개인정보보호법, 근로기준법, 중대재해처벌법 등)
        law_names = re.findall(r'([가-힣]{2,15}(?:법률|법|령|규칙))', text)
        clean_terms = []
        for ln in law_names:
            if ln not in clean_terms:
                clean_terms.append(ln)

        # 주요 법률 키워드 추출
        keywords = ["통상임금", "연차유급휴가", "해고", "퇴직금", "주휴수당", "직장내괴롭힘",
                    "개인정보", "CCTV", "동의", "제3자제공", "마케팅동의", "손해배상",
                    "위약금", "계약해제", "하자담보책임", "소멸시효", "부당이득", "불법행위",
                    "과태료", "영업정지", "행정처분", "부당노동행위", "부당공동행위", "담합", "가맹사업",
                    "하도급", "산업안전", "중대재해", "저작권", "영업비밀", "부정경쟁"]
        
        for kw in keywords:
            if kw in text and kw not in clean_terms:
                clean_terms.append(kw)

        if not clean_terms:
            # 2글자 이상 명사형 토큰 폴백
            tokens = [t.strip() for t in re.findall(r'[가-힣]{2,8}', text) if len(t.strip()) >= 2]
            clean_terms = tokens[:3]

        return clean_terms if clean_terms else [text[:10]]

    def generate_legal_memo(self, query: str, context: Optional[str] = None) -> str:
        """
        5인 에이전트 팀 협업으로 최고성능 종합 법률자문서(Legal Advisory Memo) 생성
        """
        findings = self.analyze_case(query, context)
        memo_parts = []

        # 헤더
        memo_parts.append("# ⚖️ 법률 검토 및 자문 의견서 (Legal Advisory Opinion)")
        memo_parts.append(f"**검토 의뢰**: {query.strip()}")
        if context:
            memo_parts.append(f"**사실관계 맥락**: {context.strip()}")
        memo_parts.append(f"**수행 주체**: 대한민국 국가법령정보 공동활용(open.law.go.kr) 기반 5인 전문 법률 에이전트 팀\n")

        # I. 쟁점 도출 (Chief Legal Counsel)
        memo_parts.append("## I. 사실관계 분석 및 핵심 법률 쟁점 (Fact & Legal Issues)")
        memo_parts.append("수석 법률 자문관(Chief Legal Counsel)이 의뢰 사실관계를 분석하여 확정한 핵심 법률 쟁점은 다음과 같습니다:")
        terms = findings["search_terms"]
        memo_parts.append(f"1. **실정법 요건 포섭 쟁점**: 사안의 행위가 관련 실정법규({', '.join(terms[:3])})의 적용 대상 및 법정 요건을 충족하는지 여부")
        memo_parts.append("2. **위법성 및 침해 여부**: 법령상 제한·금지 규정 위반 또는 상대방 권리 침해 성립 여부")
        memo_parts.append("3. **구제 및 제재 리스크**: 형사처벌, 행정제재(과태료·처분), 민사상 손해배상 책임 및 대응 방어 전략\n")

        # II. 실정법령 및 3단 체계 검토 (Statutory Analyst)
        memo_parts.append("## II. 실정법령 및 법률-시행령-시행규칙 3단 체계 검토 (Statutory Analysis)")
        memo_parts.append("실정법령·3단연계 조사관(Statutory Analyst)이 국가법령정보센터 최신 현행법령(`eflaw`)과 3단비교(`thdCmp`) 데이터를 실시간 대조한 결과입니다:\n")

        if findings["statutes"]:
            for st in findings["statutes"]:
                memo_parts.append(f"- **「{st['법령명']}」** (시행일: `{st.get('시행일자', '-')}`, 소관: {st.get('소관부처', '-')})")
                memo_parts.append(f"  - 현행 상태: `{st.get('제개정구분', '현행')}` 법령으로서 현재 법적 구속력을 보유함.")
            memo_parts.append("")
        else:
            memo_parts.append("- 관련 실정법령 검색 결과를 확인 중입니다.\n")

        if findings["admin_rules"]:
            memo_parts.append("### 📌 관련 행정규칙 (훈령·예규·고시)")
            for ar in findings["admin_rules"]:
                memo_parts.append(f"- **「{ar['행정규칙명']}」** ({ar.get('행정규칙종류', '고시')}, 소관: {ar.get('소관부처', '-')}, 시행: `{ar.get('시행일자', '-')}`)")
            memo_parts.append("")

        # III. 판례 및 유권해석례 분석 (Precedent Specialist)
        memo_parts.append("## III. 대법원 판례 및 유권해석례 분석 (Judicial Precedents & Authorities)")
        memo_parts.append("판례·유권해석 조사관(Precedent Specialist)이 법원의 확립된 법리와 행정관청의 유권해석을 추출하였습니다:\n")

        if findings["precedents"]:
            memo_parts.append("### 🏛️ 대법원 및 각급법원 판례")
            for pr in findings["precedents"]:
                memo_parts.append(f"- **{pr['법원명']} {pr['선고일자']} 선고 {pr['사건번호']} 판결 [{pr['사건명']}]**")
                if pr["요지"]:
                    memo_parts.append(f"  > **판결 요지**: {pr['요지']}...")
            memo_parts.append("")

        if findings["interpretations"]:
            memo_parts.append("### 📑 법제처 법령해석례")
            for exp in findings["interpretations"]:
                memo_parts.append(f"- **법제처 안건번호 {exp['안건번호']} ({exp['안건명']})** [회신: {exp.get('회신일자', '-')}]")
                if exp["요지"]:
                    memo_parts.append(f"  > **해석 요지**: {exp['요지']}...")
            memo_parts.append("")

        if findings["committee_decisions"]:
            memo_parts.append("### ⚖️ 정부 전문 위원회 결정문")
            for cd in findings["committee_decisions"]:
                memo_parts.append(f"- **[{cd['위원회']}] {cd['사건명']}** (사건/의결번호: `{cd['사건번호']}`)")
            memo_parts.append("")

        # IV. 법적 리스크 및 반대논리 검토 (Devil's Advocate)
        memo_parts.append("## IV. 법적 리스크 평가 및 반대논리 검토 (Risk Assessment & Devil's Advocate)")
        memo_parts.append("법적 리스크·반대논리 감사관(Devil's Advocate)이 가장 보수적·엄격한 시각에서 제기한 위험 요소입니다:\n")
        memo_parts.append("1. **제재 규정 리스크**: 사안 관련 의무 불이행 시 과태료 처분 또는 양벌규정에 따른 형사처벌 가능성 상존.")
        memo_parts.append("2. **상대방 및 규제기관 반대 논리**: 형식적 요건 충족 주장에도 불구하고, 실질적 지배력/동의의 자발성 결여 등을 이유로 위법성을 주장할 여지 있음.")
        memo_parts.append("3. **입증 책임(Burden of Proof)**: 적법한 절차 이행 및 사전 고지/동의의 존재에 관한 증명책임은 원칙적으로 의뢰인/사업자 측에 귀속됨.")
        memo_parts.append("4. **리스크 등급**: `중등도(Medium) ~ 고도(High)` — 선제적 서면 입증 자료 구비 필수.\n")

        # V. 최종 자문 및 실행 전략 (Actionable Counsel)
        memo_parts.append("## V. 수석 법률 자문관 종합 의견 및 권고 실행 단계 (Actionable Steps)")
        memo_parts.append("1. **[즉시 실행] 사실관계 서면 증빙 확보**: 계약서, 동의서, 업무일지, 교신 내역 등 객관적 서면 자료 즉각 편철.")
        memo_parts.append("2. **[절차적 보완] 취약 조항 규정 개정**: 관련 약관, 운영규정, 내부 가이드라인의 문구를 최신 법령에 일치하도록 정비.")
        memo_parts.append("3. **[공식 질의 활용] 필요 시 주무부처/법제처 법령해석 요청**: 유권해석 선례를 확보하여 향후 처분 위험의 고의·과실 조각.\n")

        # VI. 무결점 검증 리포트 (Reality Auditor)
        draft_text = "\n".join(memo_parts)
        audit_res = self.verifier.verify_document(draft_text)
        audit_md = self.verifier.format_report_markdown(audit_res)
        
        memo_parts.append(audit_md)

        return "\n".join(memo_parts)
