# 국가법령정보 공동활용 (open.law.go.kr) OpenAPI 기술 규격서

## 1. 기본 접속 정보
- **목록 검색 베이스 URL**: `https://www.law.go.kr/DRF/lawSearch.do`
- **본문 조회 베이스 URL**: `https://www.law.go.kr/DRF/lawService.do`
- **인증키(OC)**:
  - 테스트 공개키: `OC=test` (별도 신청 없이 즉시 호출 가능)
  - 상용 발급키: 회원가입 후 마이페이지에서 발급받은 사용자 ID(`OC=사용자ID`)
  - 환경변수: `LAW_OPENAPI_OC`
- **응답 포맷**: `type=JSON` (권장) 또는 `type=XML`, `type=HTML`

---

## 2. 주요 대상별(target) API 매핑 표

| 구분 | Target 코드 | 검색 URL (`lawSearch.do`) | 본문 URL (`lawService.do`) | 주요 파라미터 |
| :--- | :--- | :--- | :--- | :--- |
| **현행법령** | `eflaw` | `target=eflaw&query=...` | `target=law&MST=...` | `query`, `page`, `display`, `MST`, `ID` |
| **법령전체** | `law` | `target=law&query=...` | `target=law&MST=...` | `query`, `MST` |
| **공포법령** | `nwlaw` | `target=nwlaw&query=...` | `target=law&MST=...` | `query`, `MST` |
| **3단비교** | `thdCmp` | `target=thdCmp&query=...` | `target=thdCmp&MST=...&knd=2` | 법률-시행령-시행규칙 연계 |
| **판례** | `prec` | `target=prec&query=...` | `target=prec&ID=...` | `query`, `ID`, `page`, `display` |
| **헌재결정례** | `detc` | `target=detc&query=...` | `target=detc&ID=...` | `query`, `ID` |
| **법령해석례** | `expc` | `target=expc&query=...` | `target=expc&ID=...` | `query`, `ID` |
| **행정규칙** | `admrul` | `target=admrul&query=...` | `target=admrul&ID=...` | 훈령·예규·고시 |
| **자치법규** | `ordin` | `target=ordin&query=...` | `target=ordin&ID=...` | 지자체 조례·규칙 |
| **행정심판례** | `decc` | `target=decc&query=...` | `target=decc&ID=...` | 행정심판 재결례 |
| **조세심판원** | `specialDeccTt` | `target=specialDeccTt&query=...` | `target=specialDeccTt&ID=...` | 특별행정심판 |
| **소청심사위** | `specialDeccAdap` | `target=specialDeccAdap&query=...` | `target=specialDeccAdap&ID=...` | 공무원 소청심사 |
| **개인정보보호위** | `ppc` | `target=ppc&query=...` | `target=ppc&ID=...` | 12대 전문 위원회 |
| **공정거래위** | `ftc` | `target=ftc&query=...` | `target=ftc&ID=...` | 부당공동행위, 하도급 등 |
| **노동위원회** | `nlrc` | `target=nlrc&query=...` | `target=nlrc&ID=...` | 부당해고, 부당노동행위 |
| **금융위원회** | `fsc` | `target=fsc&query=...` | `target=fsc&ID=...` | 자본시장법 등 |
| **국민권익위** | `acr` | `target=acr&query=...` | `target=acr&ID=...` | 고충민원, 부패방지 |
| **방통위원회** | `kcc` | `target=kcc&query=...` | `target=kcc&ID=...` | 방송통신 심의결정문 |
| **산재심사위** | `iaciac` | `target=iaciac&query=...` | `target=iaciac&ID=...` | 산재재심사 |

---

## 3. 부처별 법령해석례 Target 코드 (cgmExpc 계열)
- 고용노동부: `cgmExpcMoel`
- 국토교통부: `cgmExpcMolit`
- 기획재정부: `cgmExpcMoef`
- 행정안전부: `cgmExpcMois`
- 환경부: `cgmExpcMe`
- 국세청: `cgmExpcNts`
- 관세청: `cgmExpcKcs`
- 교육부: `cgmExpcMoe`
- 보건복지부: `cgmExpcMohw`
- 공정거래위원회: `cgmExpcFtc`
- 경찰청: `cgmExpcNpa`
- 조달청: `cgmExpcPps`
- 질병관리청: `cgmExpcKdca`
- 법무부: `cgmExpcMoj`
- 중소벤처기업부: `cgmExpcMss`

---

## 4. 조문 파싱 핵심 데이터 스키마
`target=law&MST=...&type=JSON` 호출 시 반환되는 조문 구조:
```json
{
  "법령": {
    "기본정보": {
      "법령ID": "011357",
      "법령명_한글": "개인정보 보호법",
      "시행일자": "20260911",
      "소관부처": "개인정보보호위원회"
    },
    "조문": {
      "조문단위": [
        {
          "조문번호": "15",
          "조문가지번호": "00",
          "조문제목": "개인정보의 수집ㆍ이용",
          "조문내용": "제15조(개인정보의 수집ㆍ이용)",
          "항": [
            {
              "항번호": "①",
              "항내용": "① 개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우에는...",
              "호": [
                {
                  "호번호": "1.",
                  "호내용": "1. 정보주체의 동의를 받은 경우",
                  "목": []
                }
              ]
            }
          ]
        }
      ]
    }
  }
}
```
