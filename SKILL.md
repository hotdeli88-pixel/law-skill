---
name: law
description: "[지원 종료 — legal-ultra v2 로 통합됨] 이 스킬은 더 이상 법률 검토에 쓰지 않는다. 법률 검토·자문·의견서·조문/판례 확인·인용 검증 요청은 legal-ultra 스킬을 사용할 것. 이 스킬의 인용 검증기는 존재하지 않는 조문·판례를 통과시키는 결함이 확인되었다."
metadata:
  version: "1.0.1-deprecated"
  superseded_by: "legal-ultra 2.0.0 (https://github.com/hotdeli88-pixel/legal-ultra)"
---

# ⚠️ 지원 종료: `law` 스킬 → `legal-ultra` v2

이 스킬은 [legal-ultra v2](https://github.com/hotdeli88-pixel/legal-ultra)로 **통합**되었다. 법률 관련 요청을 받으면 이 스킬 대신
`legal-ultra` 스킬을 사용하고, 설치되어 있지 않으면 사용자에게 설치를 안내한다.

## 왜 쓰면 안 되나 (2026-09-28 적대적 검토 요약)

| 결함 | 결과 |
|---|---|
| 조문 정규식이 `제76조의2`의 `의2`를 버림 | 존재하지 않는 `근로기준법 제76조의9`가 제76조로 대조되어 **PASSED** |
| 판례 검증이 사건번호 불일치 시 첫 검색결과를 반환 | 가공 사건번호가 다른 판례로 **PASSED** |
| `제60조 및 제999조` 나열의 두 번째 인용 누락, 인용 0건이면 100% PASSED | 검증 범위가 조용히 줄어듦 |
| API 접속 실패를 "불일치"로 표시 | 실존 조문에 환각 누명 |
| `review` 자문서의 리스크·권고 절이 모든 사안 동일한 고정 문구 | "5인 에이전트 분석"이 실제 분석이 아님 |
| 부처 해석·특별행정심판 target 코드가 뒤집혀 있고, 자치법규·헌재 검색은 응답 태그 오류로 항상 0건 | 조회 실패가 "자료 없음"으로 둔갑 |

재현 근거와 전체 목록: legal-ultra 저장소 `docs/REVIEW-2026-09-28.md`.

## 이전(migration)

```bash
# 1) 이 스킬 제거(같은 요청에서 두 스킬이 경합하지 않도록)
rm -rf ~/.claude/skills/law        # 설치 위치에 맞게
# 2) 통합 스킬 설치
git clone https://github.com/hotdeli88-pixel/legal-ultra ~/.claude/skills/legal-ultra
python3 ~/.claude/skills/legal-ultra/scripts/legal.py setup
```

| v1 `law_cli.py` | v2 `legal.py` |
|---|---|
| `article "근로기준법" 60` | `article 근로기준법 60 [--hang N] [--as-of D]` (시행일 판정 포함) |
| `thdcmp "…"` | `thdcmp "…"` 또는 `delegated "…" <조> --api` |
| `precedent 2023다216777` | `precedent 2023다216777` (precedent-kr 오프라인 색인 + DRF) |
| `interpretation "개인정보"` | `interpretation "개인정보" [--target moelCgmExpc]` |
| `search "CCTV" --target ppc` | `decision ppc "CCTV"` |
| `review "…"` | 작업판(`legal_swarm.py init …`)으로 6개 역할 팀 실행 |
| `verify 문서.md` | `verify 문서.md --as-of D` (0=PASS 1=FAIL 2=INCOMPLETE) |
