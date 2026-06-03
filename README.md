# NYLB 시장조사 도구

무료 공식 API로 SNS·검색 트렌드를 수집하고 Claude Code가 분석·리포트를 작성하는 온디맨드 도구.

## 설치
```
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -e ".[dev]"
```

## 설정
1. `.env.example`를 `.env`로 복사하고 키를 채운다(YouTube/Naver 필수, Instagram 선택).
2. `config/lenses.yaml`에서 키워드·해시태그를 매장에 맞게 수정.

## 사용
```
python -m nylb scan --lens menu        # 수집 → data/raw/<run_id>.json + .digest.md
```
Claude Code에서: `/trend-scan 베이글 신메뉴`  → 수집 후 분석 리포트(`reports/`) 생성.

## 테스트
```
pytest            # 단위·통합
pytest -m live    # 실제 API 호출(키 필요)
```
