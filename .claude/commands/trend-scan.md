---
description: NYLB 시장 트렌드 스캔 — 수집 후 결정론 의사결정 상황판 자동 생성 (LLM 평결 없음)
---

사용자가 `/trend-scan <키워드/렌즈 힌트>`로 호출했습니다. 인자: $ARGUMENTS

**원칙: 시장의 판단은 사용자(사장님) 고유 영역.** 이 명령은 수치를 *검증·맥락화*해 상황판으로 정리할 뿐, 평결·추천을 작성하지 않습니다.

수행 절차:
1. 인자에서 렌즈를 정한다(기본 `menu`). 필요하면 `config/lenses.yaml` 키워드를 잠시 조정해도 된다.
2. 수집 실행: `python -m nylb scan --lens <lens> --store nylb` → 출력의 `run_id` 확인(부분 실패 허용).
3. 상황판 생성: `python -m nylb report-html --run <run_id>` → `reports/<run_id>.analysis.html` 자동 생성.
   - 보드는 **100% 데이터-주도**(검증 게이트 + 컨텍스트화)로 만들어진다. synthesis JSON을 작성하지 않는다.
   - 미검증 급상승어(예: 없는 브랜드)는 자동으로 "미검증 원시신호" 칸에 격리된다.
4. 생성된 HTML 경로를 사용자에게 알린다. 해석·결정은 사용자가 보드를 보고 직접 내린다.

로컬 상시 사용은 `python -m nylb dashboard`(버튼 클릭) 경로를 안내한다.
