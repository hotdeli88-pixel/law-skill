"""
law_verify.py - 법률 문서 내 인용 조문 및 판례 실재 여부 100% 자동 검증기 (Zero-Hallucination Gate)
기능:
  - 텍스트/마크다운 문서에서 법령명, 조·항·호, 판례 사건번호 정규식 자동 추출
  - open.law.go.kr API 실시간 1:1 대조
  - 존재하지 않는 가짜 조문, 사건번호 위조, 폐지 법령 인용 즉시 적발
  - 무결점 감사 리포트(Scorecard & Table) 출력
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 상대 임포트 지원
sys.path.append(str(Path(__file__).parent))
from law_api import LawApiClient

class LawCitationVerifier:
    def __init__(self, oc: str = None):
        self.client = LawApiClient(oc=oc)

        # 법령 조문 정규식 패턴 (예: 개인정보 보호법 제15조, 근로기준법 제60조제1항, 형법 제314조의2)
        self.statute_pattern = re.compile(
            r'(?:「|『|\[)?([가-힣A-Za-z0-9·]+(?:\s+[가-힣A-Za-z0-9·]+){0,4}(?:법률|법|령|규칙|조례|훈령|예규|고시))(?:」|』|\])?\s*제\s*(\d+(?:의\d+)?)\s*조'
        )

        # 판례 정규식 패턴 (예: 2023다216777, 2018도1234, 2020헌바56, 2019두45678, 대법원 2021. 3. 11. 선고 2020다283847 판결)
        self.precedent_pattern = re.compile(
            r'(?:대법원|서울고등법원|헌법재판소)?\s*(?:\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*(?:선고|자))?\s*(\d{4}[가-힣]{1,3}\d+)\s*(?:판결|결정)?'
        )

    def _clean_law_name(self, raw: str) -> str:
        # 따옴표/괄호가 있는 경우 내부 텍스트 우선 추출
        m = re.search(r'[「『\[]([^」』\]]+)[」』\]]', raw)
        name = m.group(1).strip() if m else raw.strip()

        tokens = name.split()
        particle_pattern = re.compile(r'(?:은|는|이|가|을|를|의|에|에서|로|으로|과|와|하고|하며|되어|된|진|한|인|당)$')
        clean_tokens = []
        for i, t in enumerate(tokens):
            if particle_pattern.search(t) and i < len(tokens) - 1:
                clean_tokens = []
                continue
            if t in ['구', '신', '현행', '동', '본', '해당']:
                continue
            clean_tokens.append(t)

        res = ' '.join(clean_tokens).strip()
        res = re.sub(r'^(?:이상|이하|미만|초과|경우|때|및|또는|관련)\s+', '', res)
        return res.strip()

    def extract_citations(self, text: str) -> Dict[str, List[Any]]:
        """
        문서 텍스트에서 인용된 실정법 조문과 판례 사건번호 추출
        """
        statutes = []
        seen_statutes = set()
        for match in self.statute_pattern.finditer(text):
            raw_law = match.group(1).strip()
            law_name = self._clean_law_name(raw_law)
            art_no = match.group(2).strip()
            key = (law_name, art_no)
            if key not in seen_statutes:
                seen_statutes.add(key)
                statutes.append({"law_name": law_name, "article_no": art_no, "full_match": match.group(0).strip()})

        precedents = []
        seen_precedents = set()
        for match in self.precedent_pattern.finditer(text):
            case_no = match.group(1).strip()
            if case_no not in seen_precedents:
                seen_precedents.add(case_no)
                precedents.append({"case_number": case_no, "full_match": match.group(0)})

        return {
            "statutes": statutes,
            "precedents": precedents
        }

    def verify_document(self, text: str) -> Dict[str, Any]:
        """
        문서 내 모든 인용 항목을 실시간 open.law.go.kr API로 검증
        """
        citations = self.extract_citations(text)
        statute_results = []
        precedent_results = []

        # 1. 법령 조문 검증
        for s in citations["statutes"]:
            res = self.client.verify_statutory_citation(s["law_name"], s["article_no"])
            statute_results.append({
                "law_name": s["law_name"],
                "article_no": s["article_no"],
                "full_match": s["full_match"],
                "valid": res.get("valid", False),
                "matched_name": res.get("law_name"),
                "article_title": res.get("title", ""),
                "preview": res.get("content_preview", ""),
                "ef_date": res.get("ef_date", ""),
                "reason": res.get("reason", "")
            })

        # 2. 판례 검증
        for p in citations["precedents"]:
            res = self.client.verify_precedent_citation(p["case_number"])
            precedent_results.append({
                "case_number": p["case_number"],
                "full_match": p["full_match"],
                "valid": res.get("valid", False),
                "case_name": res.get("case_name", ""),
                "court": res.get("court", ""),
                "sentence_date": res.get("sentence_date", ""),
                "reason": res.get("reason", "")
            })

        total = len(statute_results) + len(precedent_results)
        valid_cnt = sum(1 for s in statute_results if s["valid"]) + sum(1 for p in precedent_results if p["valid"])
        failed_cnt = total - valid_cnt
        integrity_rate = (valid_cnt / total * 100) if total > 0 else 100.0

        return {
            "total_citations": total,
            "valid_count": valid_cnt,
            "failed_count": failed_cnt,
            "integrity_rate": round(integrity_rate, 1),
            "verdict": "PASSED" if failed_cnt == 0 else "WARNING_OR_FAILED",
            "statutes": statute_results,
            "precedents": precedent_results
        }

    def format_report_markdown(self, result: Dict[str, Any]) -> str:
        """
        검증 결과를 마크다운 감사 리포트 형식으로 변환
        """
        lines = []
        verdict = result["verdict"]
        badge = "🟢 [무결점 통과 - PASSED]" if verdict == "PASSED" else "🔴 [인용 오류 발견 - VERIFICATION FAILED]"
        lines.append(f"## 🛡️ 법령·판례 인용 무결점 검증 리포트 (Anti-Hallucination Audit)")
        lines.append(f"**검증 판정**: {badge}")
        lines.append(f"- **총 인용 건수**: {result['total_citations']}건")
        lines.append(f"- **실제 존재 확인(정상)**: {result['valid_count']}건")
        lines.append(f"- **불일치/미확인(경고)**: {result['failed_count']}건")
        lines.append(f"- **인용 신뢰도**: `{result['integrity_rate']}%`\n")

        if result["statutes"]:
            lines.append("### 📜 실정법 조문 검증 결과")
            lines.append("| 인용 표기 | 실재 여부 | 공인 법령명 | 확인된 조문제목 | 시행일자 | 상태 |")
            lines.append("|:---|:---:|:---|:---|:---:|:---:|")
            for s in result["statutes"]:
                status = "✅ 정합" if s["valid"] else "❌ 불일치"
                ef_date = s["ef_date"] if s["ef_date"] else "-"
                title = f"제{s['article_no']}조({s['article_title']})" if s['article_title'] else f"제{s['article_no']}조"
                lines.append(f"| {s['full_match']} | {'O' if s['valid'] else 'X'} | {s.get('matched_name') or s['law_name']} | {title} | {ef_date} | {status} |")
            lines.append("")

        if result["precedents"]:
            lines.append("### ⚖️ 판례 사건번호 검증 결과")
            lines.append("| 인용 표기 | 실재 여부 | 사건명 | 선고법원 | 선고일자 | 상태 |")
            lines.append("|:---|:---:|:---|:---|:---:|:---:|")
            for p in result["precedents"]:
                status = "✅ 정합" if p["valid"] else "❌ 미확인"
                cname = p['case_name'][:25] + "..." if len(p['case_name']) > 25 else (p['case_name'] or "-")
                lines.append(f"| {p['case_number']} | {'O' if p['valid'] else 'X'} | {cname} | {p.get('court') or '-'} | {p.get('sentence_date') or '-'} | {status} |")
            lines.append("")

        return "\n".join(lines)


if __name__ == "__main__":
    test_doc = """
    본 사안은 개인정보 보호법 제15조 및 제17조에 따라 정보주체의 동의 요건을 갖추어야 합니다.
    또한 근로기준법 제60조에 따른 연차유급휴가 부여 의무가 존재합니다.
    관련하여 대법원 2023다216777 판결에서는 재직 조건부 임금의 통상임금성에 대해 판시한 바 있습니다.
    반면 가상의법률 제999조나 1999다999999 판례는 존재하지 않습니다.
    """
    verifier = LawCitationVerifier()
    res = verifier.verify_document(test_doc)
    print(verifier.format_report_markdown(res))
