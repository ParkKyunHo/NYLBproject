---
description: NYLB 시장 트렌드 스캔 — 수집 후 Claude가 분석·리포트 작성
---

사용자가 `/trend-scan <키워드/렌즈 힌트> [--deep]`로 호출했습니다. 인자: $ARGUMENTS

수행 절차:
1. 인자에서 렌즈를 정한다(기본 `menu`). `--deep` 포함 여부를 기록한다.
   필요하면 `config/lenses.yaml`의 키워드를 인자에 맞게 잠시 조정해도 된다.
2. 수집 실행: `python -m nylb scan --lens <lens> --store nylb`
   - 출력의 `run_id`를 확인한다. 한 소스가 실패해도 계속(부분 실패 허용).
   - 4채널(youtube/naver/google_trends/naver_datalab) + radar(워치리스트·rising)까지 수집된다.
3. `data/raw/<run_id>.digest.md`를 읽는다(필요하면 `data/raw/<run_id>.json` 원본도).
4. **분석(synthesis) 작성:**
   - 기본(경량): Claude 단일패스로 아래 스키마의 종합분석 JSON을 직접 작성한다.
   - `--deep`: Workflow로 4관점 병렬 분석→검증→종합(5에이전트)을 돌려 동일 스키마 JSON을 얻는다.
   - 정직성 가드레일: 구글/데이터랩 시계열의 스파이크 vs 추세, 상대 스케일 한계, 표본 수를 과장하지 말 것.
   - radar(인접 트렌드)는 "베이글 접목 가능성"으로 평가해 `radar`·`menu_opportunities`에 반영.
   - synthesis 스키마(키): headline, executive_summary, trend_verdicts[{keyword,stage,momentum(up|steady|down),summary}], top_insights[{title,detail}], menu_opportunities[{name,type,why,price_suggestion}], pricing_benchmark[{item,market_price,note}], content_ideas[{format,idea,angle}], action_plan[{priority,action,rationale,impact,effort,timeframe}], risks[{risk,mitigation}], data_gaps[], radar[{trend,rising_signal,bagel_fit,angle}], chart_note(선택).
   - 작성한 JSON을 `data/raw/<run_id>.synthesis.json`(UTF-8)로 저장한다.
5. **HTML 대시보드 생성:** `python -m nylb report-html --run <run_id>` 실행 →
   `reports/<run_id>.analysis.html` 자동 생성. (chart_data + build_dashboard 사용)
6. **마크다운 리포트**도 `reports/<run_id>.md`에 작성한다(이번 주 핫 TOP·채널별 근거·왜 핫한가·액션 3~5·실패 소스 명시).
7. 저장한 산출물 경로(MD + HTML)를 사용자에게 알린다.
