"""
KOSPI 예측기 Streamlit UI
=========================
실행:
    streamlit run app.py

또는:
    ..\\backend\\.venv\\Scripts\\python.exe -m streamlit run app.py
"""

import os
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import predictor as P

st.set_page_config(
    page_title="KOSPI 예측기",
    page_icon="📈",
    layout="wide",
)

# ─── 헤더 ────────────────────────────────────────────────────────
st.title("📈 KOSPI 다음날 상승확률 예측기")
st.caption(
    "LightGBM · Walk-Forward · FinanceDataReader · "
    f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)

# ─── 사이드바 ────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")

    universe_size = st.slider(
        "유니버스 크기 (KOSPI 시총 상위)", 20, 200, 50, step=10,
        help="클수록 정확하지만 수집 오래 걸림",
    )
    horizon = st.selectbox(
        "예측 시계 (일)", [1, 3, 5, 10], index=0,
        help="N일 후 종가 상승 여부",
    )
    top_k_backtest = st.slider("백테스트 Top-K", 1, 20, 5)
    top_k_today = st.slider("오늘의 추천 종목 수", 5, 30, 10)
    cost = st.slider(
        "거래비용 (%)", 0.0, 1.0, 0.18, step=0.01,
        help="거래세 + 슬리피지",
    ) / 100

    st.divider()
    clear_cache = st.checkbox("캐시 무시 (재수집)", value=False)
    if clear_cache and os.path.isdir(P.DATA_DIR):
        if st.button("🗑️ 캐시 삭제"):
            import shutil
            shutil.rmtree(P.DATA_DIR, ignore_errors=True)
            os.makedirs(P.DATA_DIR, exist_ok=True)
            st.success("캐시 삭제됨")

    st.divider()
    run_btn = st.button("🚀 실행", type="primary", use_container_width=True)

# ─── 세션 ────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None

# ─── 실행 ────────────────────────────────────────────────────────
if run_btn:
    progress_bar = st.progress(0.0)
    status = st.empty()
    t0 = time.time()

    def cb(step, pct):
        progress_bar.progress(pct)
        status.info(f"{step}  ({pct*100:.0f}%)")

    try:
        result = P.run_pipeline(
            universe_size=universe_size,
            horizon=horizon,
            top_k_backtest=top_k_backtest,
            top_k_today=top_k_today,
            cost=cost,
            progress=cb,
        )
        result["elapsed"] = time.time() - t0
        st.session_state.result = result
        status.success(f"완료 ({result['elapsed']:.1f}초)")
    except Exception as e:
        status.error(f"실행 실패: {e}")
        st.exception(e)

# ─── 결과 표시 ───────────────────────────────────────────────────
result = st.session_state.result

if result is None:
    st.info("👈 왼쪽에서 설정 후 **실행** 버튼을 눌러주세요.")
    st.markdown(
        """
        ### 이 도구가 하는 일
        1. **KOSPI 시총 상위 N개 종목**의 5년치 일봉 수집
        2. **기술적 지표 + 거시변수**로 피처 생성 (RSI, MACD, 환율, 금리 등)
        3. **LightGBM 분류**로 다음날 상승확률 예측
        4. **Walk-Forward 백테스트**로 실전 성능 평가 (미래 누수 방지)
        5. **오늘 기준 상승확률 Top-N 종목** 추천

        ### 주의
        - 참고용. 실거래 신호 아님.
        - 거래비용 0.18% 포함이지만 작은 종목은 슬리피지 더 큼.
        - 백테스트 결과 ≠ 미래 수익.
        """
    )
    st.stop()

m = result["metrics"]

# ─── 성능 카드 ───────────────────────────────────────────────────
st.subheader("📊 백테스트 성능")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("방향 정확도", f"{m['accuracy']*100:.2f}%")
c2.metric("AUC", f"{m['auc']:.4f}")
c3.metric("CAGR", f"{m['cagr']*100:.2f}%",
          delta=f"{m['cagr']*100:.1f}%", delta_color="normal")
c4.metric("Sharpe", f"{m['sharpe']:.2f}")
c5.metric("MDD", f"{m['mdd']*100:.2f}%", delta_color="inverse")

st.caption(
    f"종목 {result['n_tickers']}개 · 거래일 {m['n_days']}일 · "
    f"Top-{m['top_k']} 전략 · 비용 {m['cost']*100:.2f}%"
)

# ─── 누적수익률 ──────────────────────────────────────────────────
st.subheader("💰 누적 수익률")
cum_df = pd.DataFrame({
    "date": m["cum"].index,
    "전략": m["cum"].values,
    "Buy & Hold": (1 + m["daily"].mean()) ** range(len(m["cum"])),
})
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=cum_df["date"], y=cum_df["전략"], name="Top-K 전략",
    line=dict(width=2),
))
fig.update_layout(
    height=400, hovermode="x unified",
    xaxis_title="", yaxis_title="누적수익(배)",
    margin=dict(l=0, r=0, t=0, b=0),
)
st.plotly_chart(fig, use_container_width=True)

# ─── 오늘 추천 + 피처 중요도 ────────────────────────────────────
col_l, col_r = st.columns([3, 2])

with col_l:
    st.subheader(f"🎯 내일 상승확률 Top-{top_k_today}")
    top = result["top"].copy()
    top["확률(%)"] = (top["proba"] * 100).round(2)
    top["가격(원)"] = top["Close"].map(lambda x: f"{x:,.0f}")
    show = top[["ticker", "종목명", "가격(원)", "확률(%)"]]

    # 확률 막대 표시
    st.dataframe(
        show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "확률(%)": st.column_config.ProgressColumn(
                "상승확률",
                format="%.2f%%",
                min_value=0,
                max_value=100,
            ),
        },
    )

    csv = result["top"].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "⬇️ CSV 다운로드", csv, "predictions.csv", "text/csv",
        use_container_width=True,
    )

with col_r:
    st.subheader("🔍 피처 중요도 Top-10")
    fi = result["feature_importance"].head(10)
    fig2 = px.bar(
        fi, x="importance", y="feature", orientation="h",
        height=400,
    )
    fig2.update_layout(
        yaxis=dict(autorange="reversed"),
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis_title="", yaxis_title="",
    )
    st.plotly_chart(fig2, use_container_width=True)

# ─── 일별 수익 분포 ──────────────────────────────────────────────
with st.expander("📉 일별 수익 분포 / 최근 30일"):
    daily = m["daily"].reset_index()
    daily.columns = ["date", "ret"]

    c1, c2 = st.columns(2)
    with c1:
        fig3 = px.histogram(daily, x="ret", nbins=50, title="일별 수익 히스토그램")
        fig3.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    with c2:
        recent = daily.tail(30).copy()
        recent["color"] = recent["ret"].apply(lambda x: "▲" if x > 0 else "▼")
        fig4 = go.Figure(go.Bar(
            x=recent["date"], y=recent["ret"] * 100,
            marker_color=["#d33" if r > 0 else "#36c" for r in recent["ret"]],
        ))
        fig4.update_layout(
            height=300, title="최근 30 거래일 수익률 (%)",
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis_title="%",
        )
        st.plotly_chart(fig4, use_container_width=True)

# ─── 디버그 ─────────────────────────────────────────────────────
with st.expander("🛠️ Raw 데이터"):
    st.write("**예측 (백테스트 구간)**")
    st.dataframe(result["pred"].tail(100), use_container_width=True, hide_index=True)
    st.write("**전체 피처 중요도**")
    st.dataframe(result["feature_importance"], use_container_width=True, hide_index=True)
