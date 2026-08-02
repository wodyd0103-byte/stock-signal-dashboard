"""
KOSPI 다음날 상승확률 예측 — LightGBM Baseline (FDR 전용)
============================================================
FinanceDataReader 만 사용 (KRX 인증 불필요).
수급 데이터는 빠짐 → 기술적 지표 + 거시변수 기반.

사용법:
    pip install -r requirements.txt
    python predictor.py

출력:
    - 백테스트 성능 (정확도, AUC, CAGR, Sharpe, MDD)
    - predictions.csv : 내일 상승확률 Top-10

모델: LightGBM 이진분류 (target = 다음날 종가 수익률 > 0)
검증: Walk-forward (분기마다 재학습)
"""

import os
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import FinanceDataReader as fdr
import lightgbm as lgb
from sklearn.metrics import accuracy_score, roc_auc_score

warnings.filterwarnings("ignore")

# ─── 설정 ────────────────────────────────────────────────────────
START = "2020-01-01"
END = datetime.today().strftime("%Y-%m-%d")
UNIVERSE_SIZE = 50    # KOSPI 시총 상위 N
HORIZON = 1           # N일 후 수익률 예측
TOP_K_BACKTEST = 5
TOP_K_TODAY = 10
COST = 0.0018         # 거래세 + 슬리피지
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# ─── 1. 데이터 수집 ──────────────────────────────────────────────
def get_universe():
    """KOSPI 시총 상위 N개 종목 (Symbol, Name)"""
    listing = fdr.StockListing("KOSPI")
    # Marcap 컬럼명이 버전마다 다름 → 후보 탐색
    cap_col = next(
        (c for c in ["Marcap", "MarketCap", "Marketcap", "시가총액"] if c in listing.columns),
        None,
    )
    if cap_col is None:
        raise RuntimeError(f"시가총액 컬럼 못 찾음. 컬럼: {list(listing.columns)}")

    listing = listing.dropna(subset=[cap_col, "Code", "Name"]).copy()
    listing[cap_col] = pd.to_numeric(listing[cap_col], errors="coerce")
    listing = listing.dropna(subset=[cap_col])
    top = listing.sort_values(cap_col, ascending=False).head(UNIVERSE_SIZE)
    return top[["Code", "Name"]].reset_index(drop=True)


def fetch_stock(code):
    """단일 종목 OHLCV. 캐싱."""
    fpath = f"{DATA_DIR}/{code}.parquet"
    if os.path.exists(fpath):
        return pd.read_parquet(fpath)
    try:
        df = fdr.DataReader(code, START, END)
        if df is None or df.empty or len(df) < 200:
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df["ticker"] = code
        df.to_parquet(fpath)
        time.sleep(0.2)
        return df
    except Exception as e:
        print(f"  skip {code}: {e}")
        return None


def fetch_macro():
    """거시변수: KOSPI 지수, USD/KRW, 국고채 3년"""
    kospi = fdr.DataReader("KS11", START, END)["Close"].rename("KOSPI")
    usdkrw = fdr.DataReader("USD/KRW", START, END)["Close"].rename("USDKRW")
    try:
        rate = fdr.DataReader("KR3YT=RR", START, END)["Close"].rename("RATE")
    except Exception:
        try:
            rate = fdr.DataReader("US10YT=X", START, END)["Close"].rename("RATE")
        except Exception:
            # 마지막 fallback: 환율로 대체
            rate = usdkrw.rename("RATE")
    macro = pd.concat([kospi, usdkrw, rate], axis=1).ffill()
    macro.index = pd.to_datetime(macro.index)
    return macro


# ─── 2. 피처 엔지니어링 ──────────────────────────────────────────
def make_features(df, macro):
    out = df.copy()
    out.index = pd.to_datetime(out.index)

    c = out["Close"]

    out["ret1"] = c.pct_change()
    out["ret5"] = c.pct_change(5)
    out["ret20"] = c.pct_change(20)
    out["vol20"] = out["ret1"].rolling(20).std()

    for w in (5, 20, 60):
        out[f"ma_dis_{w}"] = c / c.rolling(w).mean() - 1

    # RSI14
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    out["rsi14"] = 100 - 100 / (1 + gain / (loss + 1e-9))

    # MACD
    ema12 = c.ewm(span=12).mean()
    ema26 = c.ewm(span=26).mean()
    out["macd"] = ema12 - ema26
    out["macd_sig"] = out["macd"].ewm(span=9).mean()
    out["macd_hist"] = out["macd"] - out["macd_sig"]

    # 거래량 z-score
    v = out["Volume"]
    out["vol_z"] = (v - v.rolling(20).mean()) / (v.rolling(20).std() + 1e-9)

    # 고저 변동성
    out["hl_range"] = (out["High"] - out["Low"]) / out["Close"]
    out["hl_range_5"] = out["hl_range"].rolling(5).mean()

    # 거시
    out = out.join(macro, how="left").ffill()
    out["kospi_ret5"] = out["KOSPI"].pct_change(5)
    out["kospi_ret20"] = out["KOSPI"].pct_change(20)
    out["usdkrw_ret5"] = out["USDKRW"].pct_change(5)
    out["rate_chg5"] = out["RATE"].diff(5)

    # 시장상대 강도
    out["rel_strength_20"] = out["ret20"] - out["kospi_ret20"]

    # 타겟
    out["fwd_ret"] = c.pct_change(HORIZON).shift(-HORIZON)
    out["target"] = (out["fwd_ret"] > 0).astype(int)

    return out


FEATURE_COLS = [
    "ret1", "ret5", "ret20", "vol20",
    "ma_dis_5", "ma_dis_20", "ma_dis_60",
    "rsi14", "macd", "macd_sig", "macd_hist",
    "vol_z", "hl_range", "hl_range_5",
    "kospi_ret5", "kospi_ret20", "usdkrw_ret5", "rate_chg5",
    "rel_strength_20",
]


# ─── 3. Walk-Forward 학습 + 백테스트 ─────────────────────────────
def walk_forward(panel):
    df = panel.reset_index().rename(columns={"index": "date", "Date": "date"})
    if "date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=FEATURE_COLS + ["target", "fwd_ret"])

    dates = sorted(df["date"].unique())
    if len(dates) < 200:
        raise RuntimeError("데이터 부족")
    mid = len(dates) // 2
    splits = pd.date_range(dates[mid], dates[-1], freq="QS")

    preds = []
    last_model = None
    for cutoff in splits:
        nxt = cutoff + pd.offsets.QuarterBegin(startingMonth=1)
        train = df[df["date"] < cutoff]
        test = df[(df["date"] >= cutoff) & (df["date"] < nxt)]
        if len(train) < 1000 or test.empty:
            continue

        model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            num_leaves=31, subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1,
        )
        model.fit(train[FEATURE_COLS], train["target"])
        proba = model.predict_proba(test[FEATURE_COLS])[:, 1]

        seg = test[["date", "ticker", "fwd_ret", "target"]].copy()
        seg["proba"] = proba
        preds.append(seg)
        last_model = model

    if not preds:
        raise RuntimeError("백테스트 구간이 부족.")
    return pd.concat(preds, ignore_index=True), last_model


# ─── 4. 평가 ─────────────────────────────────────────────────────
def compute_metrics(pred, top_k=None, cost=None):
    top_k = top_k or TOP_K_BACKTEST
    cost = COST if cost is None else cost

    acc = accuracy_score(pred["target"], (pred["proba"] > 0.5).astype(int))
    auc = roc_auc_score(pred["target"], pred["proba"])

    daily = (
        pred.groupby("date")
        .apply(lambda g: g.nlargest(top_k, "proba")["fwd_ret"].mean())
        .dropna()
        - cost
    )
    cum = (1 + daily).cumprod()
    sharpe = daily.mean() / (daily.std() + 1e-9) * np.sqrt(252)
    mdd = (cum / cum.cummax() - 1).min()
    cagr = cum.iloc[-1] ** (252 / len(cum)) - 1 if len(cum) > 0 else 0.0

    return {
        "accuracy": float(acc),
        "auc": float(auc),
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "mdd": float(mdd),
        "n_days": int(len(daily)),
        "daily": daily,
        "cum": cum,
        "top_k": top_k,
        "cost": cost,
    }


def print_metrics(m):
    print("\n━━━━━━━━━━ 백테스트 결과 ━━━━━━━━━━")
    print(f"방향 정확도 : {m['accuracy']*100:.2f}%")
    print(f"AUC         : {m['auc']:.4f}")
    print(f"Top-{m['top_k']} 전략 (수수료 {m['cost']*100:.2f}% 차감 후)")
    print(f"  CAGR    : {m['cagr']*100:.2f}%")
    print(f"  Sharpe  : {m['sharpe']:.2f}")
    print(f"  MDD     : {m['mdd']*100:.2f}%")
    print(f"  거래일수: {m['n_days']}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


# ─── 5. 오늘의 추천 ──────────────────────────────────────────────
def compute_today_top(model, panel, name_map, top_k=None):
    top_k = top_k or TOP_K_TODAY
    latest = panel.groupby("ticker").tail(1).dropna(subset=FEATURE_COLS).copy()
    latest["proba"] = model.predict_proba(latest[FEATURE_COLS])[:, 1]
    top = latest.nlargest(top_k, "proba")[["ticker", "Close", "proba"]].copy()
    top["종목명"] = top["ticker"].map(name_map).fillna("")
    top = top[["ticker", "종목명", "Close", "proba"]]
    top["proba"] = top["proba"].round(4)
    return top


def feature_importance(model):
    return pd.DataFrame(
        {"feature": FEATURE_COLS, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)


# ─── 파이프라인 (CLI + UI 공통) ──────────────────────────────────
def run_pipeline(
    universe_size=UNIVERSE_SIZE,
    horizon=HORIZON,
    top_k_backtest=TOP_K_BACKTEST,
    top_k_today=TOP_K_TODAY,
    cost=COST,
    progress=None,
):
    """전체 실행. progress(step:str, pct:float) 콜백 옵션."""
    global UNIVERSE_SIZE, HORIZON
    UNIVERSE_SIZE = universe_size
    HORIZON = horizon

    def _p(step, pct):
        if progress:
            progress(step, pct)

    _p("유니버스 선정", 0.05)
    uni = get_universe()
    tickers = uni["Code"].tolist()
    name_map = dict(zip(uni["Code"], uni["Name"]))

    _p("거시변수 수집", 0.15)
    macro = fetch_macro()

    panels = []
    n = len(tickers)
    for i, t in enumerate(tickers, 1):
        df = fetch_stock(t)
        if df is None:
            continue
        panels.append(make_features(df, macro))
        _p(f"종목 데이터 {i}/{n}", 0.15 + 0.65 * i / n)
    if not panels:
        raise RuntimeError("데이터 수집 실패")
    panel = pd.concat(panels)

    _p("학습 + 백테스트", 0.85)
    pred, model = walk_forward(panel)

    _p("결과 집계", 0.95)
    metrics = compute_metrics(pred, top_k=top_k_backtest, cost=cost)
    top = compute_today_top(model, panel, name_map, top_k=top_k_today)
    fi = feature_importance(model)

    _p("완료", 1.0)
    return {
        "metrics": metrics,
        "top": top,
        "feature_importance": fi,
        "name_map": name_map,
        "n_tickers": len(panels),
        "pred": pred,
        "model": model,
    }


# ─── CLI ────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("[*] 실행 중...")
    result = run_pipeline(progress=lambda s, p: print(f"  [{p*100:5.1f}%] {s}"))
    print_metrics(result["metrics"])
    print(f"\n━━━━━━━━━━ 내일 상승확률 Top-{TOP_K_TODAY} ━━━━━━━━━━")
    print(result["top"].to_string(index=False))
    result["top"].to_csv("predictions.csv", index=False, encoding="utf-8-sig")
    print("\n저장 완료: predictions.csv")
    print(f"\n총 소요: {time.time() - t0:.1f}초")


if __name__ == "__main__":
    main()
