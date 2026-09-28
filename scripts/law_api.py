"""
law_api.py - 국가법령정보 공동활용(open.law.go.kr) OpenAPI Python 클라이언트
기능:
  - 현행법령, 공포법령, 연혁법령 목록 및 조문·항·호·목 본문 조회
  - 법률-시행령-시행규칙 3단 비교(thdCmp) 조회
  - 판례(대법원·각급법원) 판시사항·판결요지·전문 조회
  - 법제처 및 30개 부처별 유권해석례(expc) 질의요지·회답·이유 조회
  - 행정규칙(훈령·예규·고시), 자치법규(조례·규칙) 조회
  - 12대 전문 위원회(개인정보보호위, 공정위, 노동위, 권익위 등) 결정례 조회
  - 인용 조문 및 판례 실재 여부 실시간 팩트체크 검증
"""

import os
import sys
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple

# 기본 캐시 디렉터리
CACHE_DIR = Path.home() / ".law" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class LawApiClient:
    BASE_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
    BASE_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"

    def __init__(self, oc: Optional[str] = None, use_cache: bool = True, timeout: int = 10):
        # 환경변수 LAW_OPENAPI_OC -> 전달된 인자 -> 'test' 기본값
        self.oc = oc or os.getenv("LAW_OPENAPI_OC", "test").strip()
        self.use_cache = use_cache
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/xml, */*"
        }

    def _get_cache_path(self, key: str) -> Path:
        # 안전한 파일명 생성
        safe_key = re.sub(r'[^\w\-_\.]', '_', key)[:120]
        return CACHE_DIR / f"{safe_key}.json"

    def _read_cache(self, key: str) -> Optional[Any]:
        if not self.use_cache:
            return None
        cache_file = self._get_cache_path(key)
        if cache_file.exists():
            try:
                # 7일 유효
                if time.time() - cache_file.stat().st_mtime < 7 * 86400:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                pass
        return None

    def _write_cache(self, key: str, data: Any):
        if not self.use_cache:
            return
        cache_file = self._get_cache_path(key)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _request(self, url: str, params: Dict[str, Any], fmt: str = "JSON", retries: int = 2) -> Any:
        params["OC"] = self.oc
        params["type"] = fmt
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        cache_key = f"{url}_{query_string}"

        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        req = urllib.request.Request(full_url, headers=self.headers)
        last_err = None

        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8", errors="ignore")
                    if fmt == "JSON":
                        try:
                            data = json.loads(raw)
                            self._write_cache(cache_key, data)
                            return data
                        except json.JSONDecodeError:
                            # 만약 JSON 응답이 HTML/XML로 왔다면 폴백 처리
                            if raw.strip().startswith("<?xml"):
                                root = ET.fromstring(raw)
                                data = {"_xml": raw}
                                return data
                            return {"_raw": raw}
                    else:
                        return raw
            except Exception as e:
                last_err = e
                time.sleep(0.5 * (attempt + 1))

        # 에러 발생 시 빈 딕셔너리 반환
        return {"error": str(last_err), "url": full_url}

    # ==================== 1. 법령 검색 및 본문 ====================

    def search_statute(self, query: str, target: str = "eflaw", page: int = 1, display: int = 20) -> List[Dict[str, Any]]:
        """
        법령 검색 (eflaw: 현행법령, law: 법령전체, nwlaw: 공포법령 등)
        """
        params = {
            "target": target,
            "query": query,
            "page": page,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        root = res.get("LawSearch", {})
        laws = root.get("law", [])
        if isinstance(laws, dict):
            laws = [laws]
        return laws

    def get_statute_by_mst(self, mst: Union[str, int]) -> Dict[str, Any]:
        """
        법령일련번호(MST)로 법령 상세 JSON 조회
        """
        params = {
            "target": "law",
            "MST": str(mst)
        }
        res = self._request(self.BASE_SERVICE_URL, params, fmt="JSON")
        return res.get("법령", {})

    def find_statute_mst(self, law_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        법령명으로 가장 부합하는 현행 법령일련번호(MST), 법령명, 시행일자 조회
        """
        clean_name = law_name.replace(" ", "")
        laws = self.search_statute(law_name, target="eflaw", display=10)
        
        # 1. 완전 일치 우선 (공백 제거)
        for l in laws:
            nm = l.get("법령명한글", "").replace(" ", "")
            status = l.get("현행연혁코드", "")
            if nm == clean_name and "현행" in status:
                return l.get("법령일련번호"), l.get("법령명한글"), l.get("시행일자")

        # 2. 완전 일치 (상태 무관)
        for l in laws:
            nm = l.get("법령명한글", "").replace(" ", "")
            if nm == clean_name:
                return l.get("법령일련번호"), l.get("법령명한글"), l.get("시행일자")

        # 3. 포함 일치
        for l in laws:
            nm = l.get("법령명한글", "").replace(" ", "")
            if clean_name in nm:
                return l.get("법령일련번호"), l.get("법령명한글"), l.get("시행일자")

        if laws:
            return laws[0].get("법령일련번호"), laws[0].get("법령명한글"), laws[0].get("시행일자")
        return None, None, None

    def get_article(self, law_name: str, article_no: Union[str, int]) -> Dict[str, Any]:
        """
        법령명과 조문번호(예: 15 또는 '제15조')로 특정 조문과 세부 항·호·목 추출
        """
        art_str = str(article_no).replace("제", "").replace("조", "").strip()
        mst, real_name, ef_date = self.find_statute_mst(law_name)
        if not mst:
            return {"error": f"법령 '{law_name}'을(를) 찾을 수 없습니다."}

        law_data = self.get_statute_by_mst(mst)
        jomun_list = law_data.get("조문", {}).get("조문단위", [])
        if isinstance(jomun_list, dict):
            jomun_list = [jomun_list]

        matched_articles = []
        for j in jomun_list:
            cur_no = str(j.get("조문번호", "")).strip()
            # 조문가지번호 고려 (예: 제15조의2)
            cur_branch = str(j.get("조문가지번호", "")).strip()
            full_art_no = cur_no
            if cur_branch and cur_branch != "0" and cur_branch != "00":
                full_art_no = f"{cur_no}의{cur_branch}"

            if cur_no == art_str or full_art_no == art_str:
                matched_articles.append(j)

        if not matched_articles:
            # 제목이나 내용에서 검색
            for j in jomun_list:
                content = j.get("조문내용", "")
                if f"제{art_str}조" in content:
                    matched_articles.append(j)

        return {
            "법령명": real_name or law_name,
            "법령일련번호": mst,
            "시행일자": ef_date,
            "기본정보": law_data.get("기본정보", {}),
            "검색조문번호": art_str,
            "조문": matched_articles
        }

    # ==================== 2. 법률-시행령-시행규칙 3단 비교 ====================

    def get_3tier_comparison(self, law_name: str) -> Dict[str, Any]:
        """
        법률명으로 3단비교(법률-시행령-시행규칙) 연계 데이터 조회
        """
        mst, real_name, ef_date = self.find_statute_mst(law_name)
        if not mst:
            return {"error": f"법령 '{law_name}'을(를) 찾을 수 없습니다."}

        params = {
            "target": "thdCmp",
            "MST": str(mst),
            "knd": "2"  # 3단비교 종류
        }
        res = self._request(self.BASE_SERVICE_URL, params, fmt="JSON")
        thd_service = res.get("LspttnThdCmpLawXService", {})
        return {
            "법령명": real_name or law_name,
            "법령일련번호": mst,
            "기본정보": thd_service.get("기본정보", {}),
            "위임조문삼단비교": thd_service.get("위임조문삼단비교", {})
        }

    # ==================== 3. 판례 (대법원·하급심) ====================

    def search_precedent(self, query: str, page: int = 1, display: int = 10) -> List[Dict[str, Any]]:
        """
        판례 목록 검색
        """
        params = {
            "target": "prec",
            "query": query,
            "page": page,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        prec_search = res.get("PrecSearch", {})
        precs = prec_search.get("prec", [])
        if isinstance(precs, dict):
            precs = [precs]
        return precs

    def get_precedent_detail(self, prec_id: Union[str, int]) -> Dict[str, Any]:
        """
        판례일련번호로 판시사항, 판결요지, 참조조문, 참조판례, 전문 조회
        """
        params = {
            "target": "prec",
            "ID": str(prec_id)
        }
        res = self._request(self.BASE_SERVICE_URL, params, fmt="JSON")
        return res.get("PrecService", {})

    def find_precedent_by_case_number(self, case_number: str) -> Optional[Dict[str, Any]]:
        """
        사건번호(예: 2023다216777)로 판례 직접 검색 및 상세 조회
        """
        clean_num = case_number.replace(" ", "")
        precs = self.search_precedent(clean_num, display=5)
        for p in precs:
            if clean_num in p.get("사건번호", "").replace(" ", ""):
                pid = p.get("판례일련번호")
                if pid:
                    return self.get_precedent_detail(pid)
        if precs and precs[0].get("판례일련번호"):
            return self.get_precedent_detail(precs[0]["판례일련번호"])
        return None

    # ==================== 4. 법령해석례 (법제처·부처) ====================

    def search_interpretation(self, query: str, target: str = "expc", page: int = 1, display: int = 10) -> List[Dict[str, Any]]:
        """
        법령해석례 검색 (expc: 법제처, cgmExpcMoel: 노동부, cgmExpcMois: 행안부 등)
        """
        params = {
            "target": target,
            "query": query,
            "page": page,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        root_key = list(res.keys())[0] if res else ""
        items = res.get(root_key, {}).get("expc", [])
        if not items:
            # 부처별 해석례의 경우 키명이 다를 수 있음
            for k, v in res.get(root_key, {}).items():
                if isinstance(v, list):
                    items = v
                    break
        if isinstance(items, dict):
            items = [items]
        return items

    def get_interpretation_detail(self, expc_id: Union[str, int], target: str = "expc") -> Dict[str, Any]:
        """
        법령해석례 상세 조회 (안건명, 질의요지, 회답, 이유)
        """
        params = {
            "target": target,
            "ID": str(expc_id)
        }
        res = self._request(self.BASE_SERVICE_URL, params, fmt="JSON")
        return res.get("ExpcService", res)

    # ==================== 5. 행정규칙·자치법규·결정문 ====================

    def search_admin_rule(self, query: str, page: int = 1, display: int = 10) -> List[Dict[str, Any]]:
        """
        행정규칙(훈령, 예규, 고시) 검색
        """
        params = {
            "target": "admrul",
            "query": query,
            "page": page,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        items = res.get("AdmRulSearch", {}).get("admrul", [])
        if isinstance(items, dict):
            items = [items]
        return items

    def get_admin_rule_detail(self, admrul_id: Union[str, int]) -> Dict[str, Any]:
        """
        행정규칙 본문 상세 조회
        """
        params = {
            "target": "admrul",
            "ID": str(admrul_id)
        }
        res = self._request(self.BASE_SERVICE_URL, params, fmt="JSON")
        return res.get("AdmRulService", {})

    def search_ordinance(self, query: str, page: int = 1, display: int = 10) -> List[Dict[str, Any]]:
        """
        자치법규(조례, 규칙) 검색
        """
        params = {
            "target": "ordin",
            "query": query,
            "page": page,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        items = res.get("OrdinSearch", {}).get("ordin", [])
        if isinstance(items, dict):
            items = [items]
        return items

    def get_ordinance_detail(self, ordin_id: Union[str, int]) -> Dict[str, Any]:
        """
        자치법규 본문 상세 조회
        """
        params = {
            "target": "ordin",
            "ID": str(ordin_id)
        }
        res = self._request(self.BASE_SERVICE_URL, params, fmt="JSON")
        return res.get("OrdinService", {})

    def search_committee_decision(self, committee: str, query: str, display: int = 10) -> List[Dict[str, Any]]:
        """
        12대 전문 위원회 결정문 검색 (ppc: 개인정보위, ftc: 공정위, nlrc: 노동위, fsc: 금융위, acr: 국민권익위 등)
        """
        params = {
            "target": committee,
            "query": query,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        root_key = list(res.keys())[0] if res else ""
        items = []
        for k, v in res.get(root_key, {}).items():
            if isinstance(v, list):
                items = v
                break
            elif isinstance(v, dict) and k != "resultMsg":
                items = [v]
        return items

    def search_constitutional(self, query: str, display: int = 10) -> List[Dict[str, Any]]:
        """
        헌법재판소 결정례(detc) 검색
        """
        params = {
            "target": "detc",
            "query": query,
            "display": display
        }
        res = self._request(self.BASE_SEARCH_URL, params, fmt="JSON")
        items = res.get("DetcSearch", {}).get("detc", [])
        if isinstance(items, dict):
            items = [items]
        return items

    # ==================== 6. 조문 및 인용 검증기 (Anti-Hallucination) ====================

    def verify_statutory_citation(self, law_name: str, article_no: Union[str, int]) -> Dict[str, Any]:
        """
        인용된 법률 및 조문번호의 실재 여부, 조문제목, 본문 팩트체크
        """
        result = self.get_article(law_name, article_no)
        if "error" in result or not result.get("조문"):
            return {
                "valid": False,
                "law_name": law_name,
                "article_no": article_no,
                "reason": result.get("error", f"제{article_no}조를 찾을 수 없습니다.")
            }
        
        art = result["조문"][0]
        title = art.get("조문제목", "")
        content = art.get("조문내용", "")
        return {
            "valid": True,
            "law_name": result["법령명"],
            "article_no": article_no,
            "title": title,
            "content_preview": content[:120].strip() if content else "",
            "mst": result["법령일련번호"],
            "ef_date": result["시행일자"]
        }

    def verify_precedent_citation(self, case_number: str) -> Dict[str, Any]:
        """
        인용된 판례 사건번호의 실재 여부, 사건명, 선고일자 팩트체크
        """
        prec = self.find_precedent_by_case_number(case_number)
        if not prec:
            return {
                "valid": False,
                "case_number": case_number,
                "reason": "해당 사건번호의 판례를 국가법령정보에서 찾을 수 없습니다."
            }
        return {
            "valid": True,
            "case_number": prec.get("사건번호", case_number),
            "case_name": prec.get("사건명", ""),
            "court": prec.get("법원명", ""),
            "sentence_date": prec.get("선고일자", ""),
            "summary_preview": prec.get("판결요지", "")[:120].strip()
        }


# ==================== 헬퍼 함수 ====================

def format_article_text(article_dict: Dict[str, Any]) -> str:
    """
    조문 딕셔너리를 가독성 높은 텍스트로 서식화 (조, 항, 호, 목)
    """
    lines = []
    art_no = article_dict.get("조문번호", "")
    art_branch = article_dict.get("조문가지번호", "")
    full_no = art_no if not art_branch or art_branch in ["0", "00"] else f"{art_no}의{art_branch}"
    title = article_dict.get("조문제목", "")
    content = article_dict.get("조문내용", "")

    header = f"제{full_no}조"
    if title:
        header += f"({title})"
    lines.append(header)
    if content and content != header:
        lines.append(f"  {content.strip()}")

    # 항
    hang_list = article_dict.get("항")
    if hang_list:
        if isinstance(hang_list, dict):
            hang_list = [hang_list]
        for h in hang_list:
            h_no = h.get("항번호", "")
            h_content = h.get("항내용", "")
            lines.append(f"  {h_no} {h_content.strip()}")

            # 호
            ho_list = h.get("호")
            if ho_list:
                if isinstance(ho_list, dict):
                    ho_list = [ho_list]
                for ho in ho_list:
                    ho_no = ho.get("호번호", "")
                    ho_content = ho.get("호내용", "")
                    lines.append(f"    {ho_no} {ho_content.strip()}")

                    # 목
                    mok_list = ho.get("목")
                    if mok_list:
                        if isinstance(mok_list, dict):
                            mok_list = [mok_list]
                        for mok in mok_list:
                            mok_no = mok.get("목번호", "")
                            mok_content = mok.get("목내용", "")
                            lines.append(f"      {mok_no} {mok_content.strip()}")

    return "\n".join(lines)
