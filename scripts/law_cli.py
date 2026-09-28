"""
law_cli.py - 대한민국 국가법령정보 공동활용(open.law.go.kr) 기반 법률 검토 CLI 도구
사용법:
  python law_cli.py search <키워드> [--target eflaw|prec|expc|admrul|ordin|ppc|ftc...]
  python law_cli.py article <법령명> <조문번호>
  python law_cli.py thdcmp <법령명>
  python law_cli.py precedent <사건번호 또는 키워드>
  python law_cli.py interpretation <안건번호 또는 키워드>
  python law_cli.py review <사안 질의> [--context <상세 사실관계>] [-o <저장 파일명>]
  python law_cli.py verify <문서파일 또는 텍스트>
"""

import sys
import os
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from law_api import LawApiClient, format_article_text
from law_verify import LawCitationVerifier
from law_team import LawAgentTeam

def main():
    parser = argparse.ArgumentParser(description="대한민국 법령·판례 기반 법률 검토 CLI (open.law.go.kr)")
    subparsers = parser.add_subparsers(dest="command", help="실행할 서브 명령")

    # 1. search
    p_search = subparsers.add_parser("search", help="법령, 판례, 유권해석례, 행정규칙, 자치법규 검색")
    p_search.add_argument("query", help="검색 키워드 (예: 개인정보, 통상임금, CCTV)")
    p_search.add_argument("--target", default="eflaw", choices=["eflaw", "law", "prec", "expc", "admrul", "ordin", "detc", "ppc", "ftc", "nlrc", "fsc"], help="검색 대상 (기본: eflaw 현행법령)")
    p_search.add_argument("--limit", type=int, default=10, help="출력 건수")

    # 2. article
    p_article = subparsers.add_parser("article", help="특정 법령의 특정 조문(제N조) 전문 및 항·호·목 조회")
    p_article.add_argument("law", help="법령명 (예: 근로기준법, 개인정보 보호법)")
    p_article.add_argument("number", help="조문번호 (예: 15, 60, 314의2)")

    # 3. thdcmp
    p_thdcmp = subparsers.add_parser("thdcmp", help="법률-시행령-시행규칙 3단 비교 조회")
    p_thdcmp.add_argument("law", help="법령명 (예: 개인정보 보호법)")

    # 4. precedent
    p_prec = subparsers.add_parser("precedent", help="판례 검색 및 사건번호 상세 조회")
    p_prec.add_argument("query", help="사건번호(예: 2023다216777) 또는 판례 검색어")

    # 5. interpretation
    p_expc = subparsers.add_parser("interpretation", help="법제처 유권해석례 검색 및 상세 조회")
    p_expc.add_argument("query", help="안건번호(예: 20-0370) 또는 해석례 검색어")

    # 6. review
    p_review = subparsers.add_parser("review", help="5인 전문 에이전트 팀 법률 검토 및 자문의견서 생성")
    p_review.add_argument("query", help="법률 검토 질의 내용")
    p_review.add_argument("--context", default=None, help="추가 사실관계 및 배경 설명")
    p_review.add_argument("-o", "--output", default=None, help="마크다운 자문서 저장 경로 (.md)")

    # 7. verify
    p_verify = subparsers.add_parser("verify", help="법률 문서 내 인용 조문 및 판례 실재 여부 100%% 자동 검증")
    p_verify.add_argument("target", help="검증할 파일 경로(.md/.txt) 또는 직접 입력 텍스트")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    client = LawApiClient()

    if args.command == "search":
        print(f"🔍 [검색 대상: {args.target}] 키워드: '{args.query}'...")
        if args.target in ["eflaw", "law"]:
            items = client.search_statute(args.query, target=args.target, display=args.limit)
            print(f"\n총 {len(items)}건 조회됨:")
            for idx, it in enumerate(items, 1):
                print(f"  {idx}. {it.get('법령명한글')} | {it.get('법령구분명', '법률')} | 시행: {it.get('시행일자', '-')} | 상태: {it.get('현행연혁코드', '현행')} (MST: {it.get('법령일련번호')})")
        elif args.target == "prec":
            items = client.search_precedent(args.query, display=args.limit)
            print(f"\n총 {len(items)}건 판례 조회됨:")
            for idx, it in enumerate(items, 1):
                print(f"  {idx}. {it.get('법원명')} {it.get('선고일자')} 선고 {it.get('사건번호')} [{it.get('사건명')}] (ID: {it.get('판례일련번호')})")
        elif args.target == "expc":
            items = client.search_interpretation(args.query, display=args.limit)
            print(f"\n총 {len(items)}건 법령해석례 조회됨:")
            for idx, it in enumerate(items, 1):
                print(f"  {idx}. 안건 {it.get('안건번호')} | {it.get('회신기관명', '법제처')} | {it.get('안건명')} (회신: {it.get('회신일자')})")
        elif args.target == "admrul":
            items = client.search_admin_rule(args.query, display=args.limit)
            print(f"\n총 {len(items)}건 행정규칙 조회됨:")
            for idx, it in enumerate(items, 1):
                print(f"  {idx}. {it.get('행정규칙명')} | {it.get('행정규칙종류명', '고시')} | 소관: {it.get('소관부처명')} (시행: {it.get('시행일자')})")
        elif args.target == "ordin":
            items = client.search_ordinance(args.query, display=args.limit)
            print(f"\n총 {len(items)}건 자치법규 조회됨:")
            for idx, it in enumerate(items, 1):
                print(f"  {idx}. {it.get('자치법규명')} | {it.get('지자체명')} (시행: {it.get('시행일자')})")
        else: # committee
            items = client.search_committee_decision(args.target, args.query, display=args.limit)
            print(f"\n총 {len(items)}건 위원회({args.target.upper()}) 결정문 조회됨:")
            for idx, it in enumerate(items, 1):
                title = it.get("사건명") or it.get("안건명") or it.get("문서명") or it.get("제목")
                print(f"  {idx}. [{args.target.upper()}] {title} (번호: {it.get('사건번호', '-')})")

    elif args.command == "article":
        res = client.get_article(args.law, args.number)
        if "error" in res or not res.get("조문"):
            print(f"❌ 오류: {res.get('error', '해당 조문을 찾을 수 없습니다.')}")
        else:
            print(f"\n📜 [{res['법령명']}] (시행일: {res.get('시행일자', '-')})")
            for j in res["조문"]:
                print("-" * 50)
                print(format_article_text(j))
            print("-" * 50)

    elif args.command == "thdcmp":
        res = client.get_3tier_comparison(args.law)
        if "error" in res:
            print(f"❌ 오류: {res.get('error')}")
        else:
            print(f"\n📑 [{res['법령명']}] 3단 비교 (법률-시행령-시행규칙 연계)")
            thd = res.get("위임조문삼단비교", {})
            law_articles = thd.get("법률조문", [])
            print(f"확인된 위임 연계 조문 수: {len(law_articles)}개")
            for la in law_articles[:5]:
                print(f"  - 제{la.get('조번호')}조 {la.get('조제목', '')}: {la.get('조내용', '')[:40]}")

    elif args.command == "precedent":
        # 만약 사건번호 형태면 바로 조회
        clean_q = args.query.replace(" ", "")
        detail = client.find_precedent_by_case_number(clean_q)
        if detail:
            print(f"\n⚖️ [{detail.get('법원명')} {detail.get('선고일자')} 선고 {detail.get('사건번호')} 판결]")
            print(f"사건명: {detail.get('사건명')}")
            print(f"판결유형: {detail.get('판결유형', '판결')}")
            print("\n[판시사항]")
            print(detail.get("판시사항", "").replace("<br/>", "\n"))
            print("\n[판결요지]")
            print(detail.get("판결요지", "").replace("<br/>", "\n")[:600] + "...")
        else:
            print(f"🔍 사건번호 불일치, 판례 키워드 검색 수행: '{args.query}'...")
            precs = client.search_precedent(args.query, display=5)
            for idx, it in enumerate(precs, 1):
                print(f"  {idx}. {it.get('법원명')} {it.get('선고일자')} 선고 {it.get('사건번호')} [{it.get('사건명')}]")

    elif args.command == "interpretation":
        items = client.search_interpretation(args.query, display=5)
        if items:
            it0 = items[0]
            eid = it0.get("법령해석례일련번호")
            if eid:
                detail = client.get_interpretation_detail(eid)
                print(f"\n📑 [법제처 법령해석 안건 {detail.get('안건번호')}]")
                print(f"안건명: {detail.get('안건명')}")
                print(f"회신기관: {detail.get('회신기관명', '법제처')} (회신일: {detail.get('회신일자')})")
                print("\n[질의요지]")
                print(detail.get("질의요지", "").replace("<br/>", "\n"))
                print("\n[회답]")
                print(detail.get("회답", "").replace("<br/>", "\n"))
        else:
            print("해당 질의에 대한 해석례가 없습니다.")

    elif args.command == "review":
        print("🏛️ [5인 전문 법률 에이전트 팀 가동] 사실관계 분석 및 종합 자문의견서 작성 중...")
        team = LawAgentTeam()
        memo = team.generate_legal_memo(args.query, args.context)
        print(memo)
        if args.output:
            out_path = Path(args.output)
            out_path.write_text(memo, encoding="utf-8")
            print(f"\n💾 자문의견서가 저장되었습니다: {out_path.resolve()}")

    elif args.command == "verify":
        text = ""
        p = Path(args.target)
        if p.exists() and p.is_file():
            text = p.read_text(encoding="utf-8")
        else:
            text = args.target

        print("🛡️ [조문 원문 대조 검증관] 인용 항목 실시간 팩트체크 검증 중...")
        verifier = LawCitationVerifier()
        result = verifier.verify_document(text)
        print(verifier.format_report_markdown(result))

if __name__ == "__main__":
    main()
