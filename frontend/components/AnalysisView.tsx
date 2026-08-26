"use client";

import { AlertCircle, CheckCircle2, Download, Plus } from "lucide-react";
import FearGreedGauge from "@/components/FearGreedGauge";
import IndicatorTable from "@/components/IndicatorTable";
import PredictionCard from "@/components/PredictionCard";
import PriceChart from "@/components/PriceChart";
import PriceTargetCard from "@/components/PriceTargetCard";
import NewsSentimentCard from "@/components/NewsSentimentCard";
import DisclosureCard from "@/components/DisclosureCard";
import LearnedSignalCard from "@/components/LearnedSignalCard";
import FundamentalCard from "@/components/FundamentalCard";
import RiskCard from "@/components/RiskCard";
import SignalCard from "@/components/SignalCard";
import SupplyDemandCard from "@/components/SupplyDemandCard";
import IndicatorGuideInline from "@/components/IndicatorGuideInline";
import BacktestSection from "@/components/BacktestSection";
import { useTickerFlipCount } from "@/hooks/queries";
import { buildStockCsvUrl, IS_DEMO } from "@/lib/api";
import type { AnalysisResponse, Period } from "@/lib/types";

interface Props {
  analysis: AnalysisResponse | null;
  loading: boolean;
  /** 조회 실패 메시지. 예전에는 토스트로 스쳐 지나가 원인을 읽을 새가 없었다. */
  error?: string | null;
  period: Period;
  onAddWatchlist: () => void;
}

export default function AnalysisView({ analysis, loading, error, period, onAddWatchlist }: Props) {
  // 훅은 아래 조기 반환보다 먼저 불러야 한다. 종목이 없으면 훅이 조회를 미룬다.
  const flipCount = useTickerFlipCount(analysis?.ticker);

  if (!analysis && loading) return <LoadingSkeleton />;
  if (!analysis && error) {
    return (
      <div role="alert" className="card text-center">
        <AlertCircle size={20} className="mx-auto text-down" />
        <p className="mt-2 text-base font-bold text-ink">분석을 불러오지 못했습니다</p>
        <p className="mt-1 text-sm text-muted">{error}</p>
      </div>
    );
  }
  if (!analysis) {
    return (
      <div className="card text-center text-sub">
        <p className="text-base font-bold text-ink">종목을 선택하세요</p>
        <p className="mt-1 text-sm text-muted">
          상단 검색 또는 좌측 발굴/관심 목록에서 종목을 고르면 분석이 표시됩니다.
        </p>
      </div>
    );
  }

  const up = analysis.change >= 0;

  return (
    <div className="stagger space-y-4">
      {/* 데이터 소스 배지 */}
      <DataSourceBanner analysis={analysis} />

      {/* 히어로 가격 */}
      <section className="card overflow-hidden">
        {/* 좁은 화면에서는 CSV/관심 묶음이 가격 아래로 내려간다. */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-muted">{analysis.ticker}</p>
            <h2 className="mt-1 text-display font-extrabold tracking-tight text-ink tabular">
              {analysis.current_price.toLocaleString()}
            </h2>
            <div className="mt-2 flex items-baseline gap-2">
              <span className={`text-lg font-bold tabular ${up ? "text-up" : "text-down"}`}>
                {up ? "+" : ""}
                {analysis.change.toLocaleString()}
              </span>
              <span
                className={`text-base font-bold tabular ${analysis.change_rate >= 0 ? "text-up" : "text-down"}`}
              >
                ({analysis.change_rate >= 0 ? "+" : ""}
                {analysis.change_rate.toFixed(2)}%)
              </span>
              <span className="text-xs text-muted">전일 대비</span>
            </div>
          </div>
          <div className="ml-auto flex min-w-0 flex-col items-end gap-2">
            <div className="flex items-center gap-2">
              <a
                href={buildStockCsvUrl(analysis.ticker, period)}
                className="btn-ghost"
                title="시계열 CSV 다운로드"
              >
                <Download size={16} />
                CSV
              </a>
              <button
                type="button"
                onClick={onAddWatchlist}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-tossStrong px-4 text-sm font-bold text-white hover:bg-toss-600"
              >
                <Plus size={16} />
                관심
              </button>
            </div>
            <p className="text-xs text-muted">거래량 {analysis.volume.toLocaleString()}</p>
          </div>
        </div>
      </section>

      {/* 차트 + 신호 */}
      <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <PriceChart data={analysis.price_history} />
        <SignalCard signal={analysis.signal} flipCount={flipCount} />
      </section>

      {/* 심리 + 목표가/매도시점 */}
      {analysis.market_sentiment ? (
        <section className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
          <FearGreedGauge sentiment={analysis.market_sentiment} />
          <PriceTargetCard
            currentPrice={analysis.current_price}
            longTerm={analysis.long_term_predictions}
            optimalExit={analysis.optimal_exit}
            priceTarget={analysis.price_target}
          />
        </section>
      ) : (
        <PriceTargetCard
          currentPrice={analysis.current_price}
          longTerm={analysis.long_term_predictions}
          optimalExit={analysis.optimal_exit}
          priceTarget={analysis.price_target}
        />
      )}

      {/* 수급 + 뉴스 (국내) */}
      {analysis.supply_demand || analysis.news_sentiment ? (
        <section className="grid gap-4 xl:grid-cols-2">
          {analysis.supply_demand ? (
            <SupplyDemandCard sd={analysis.supply_demand} sector={analysis.sector} />
          ) : null}
          {analysis.news_sentiment ? <NewsSentimentCard news={analysis.news_sentiment} /> : null}
        </section>
      ) : null}

      {/* 펀더멘털 + 공시 (국내) */}
      {analysis.fundamental || analysis.disclosure ? (
        <section className="grid gap-4 xl:grid-cols-2">
          {analysis.fundamental ? <FundamentalCard f={analysis.fundamental} /> : null}
          {analysis.disclosure ? <DisclosureCard disc={analysis.disclosure} /> : null}
        </section>
      ) : null}

      {/* 학습신호 + 리스크 */}
      <section className="grid gap-4 xl:grid-cols-2">
        {analysis.learned_signal ? <LearnedSignalCard ls={analysis.learned_signal} /> : null}
        <RiskCard risk={analysis.risk} />
      </section>

      {/* 단기예측 */}
      <PredictionCard predictions={analysis.predictions} />

      {/* 지표 */}
      <IndicatorTable indicators={analysis.indicators} />

      {/* 백테스트 (접이식) */}
      <BacktestSection ticker={analysis.ticker} period={period} />

      {/* 신호 기준 (접이식) */}
      <IndicatorGuideInline />
    </div>
  );
}

function DataSourceBanner({ analysis }: { analysis: AnalysisResponse }) {
  if (analysis.is_sample) {
    return (
      <div className="flex items-center gap-2.5 rounded-card bg-warnBg px-4 py-3 text-sm text-warn">
        <AlertCircle size={16} className="shrink-0" />
        <div className="flex-1">
          <p className="font-bold">샘플 데이터 사용 중</p>
          {analysis.provider_error ? (
            <p className="mt-0.5 text-xs">실패: {analysis.provider_error}</p>
          ) : null}
        </div>
      </div>
    );
  }
  // 데모에서는 "실시간"이라고 쓰면 안 된다. 값은 캡처해둔 시점 그대로다.
  if (IS_DEMO) {
    return (
      <div className="flex items-center gap-2.5 rounded-card bg-surface px-3 py-2 text-xs text-sub">
        <CheckCircle2 size={15} className="shrink-0" />
        <p className="font-medium">
          미리 받아둔 응답 · 원 출처 <span className="font-bold">{analysis.source}</span>
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2.5 rounded-card bg-toss-50 px-3 py-2 text-xs text-toss-700">
      <CheckCircle2 size={15} className="shrink-0" />
      <p className="font-medium">
        실시간 데이터 · 출처 <span className="font-bold">{analysis.source}</span>
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    // 스켈레톤은 눈에만 보인다. 읽어주는 쪽에는 "불러오는 중"이라고 알려야
    // 빈 화면에서 기다려야 할지 판단할 수 있다.
    <div className="space-y-4" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">분석을 불러오는 중입니다</span>
      <div className="h-32 animate-pulse rounded-card bg-surface" />
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="h-[380px] animate-pulse rounded-card bg-surface" />
        <div className="h-[380px] animate-pulse rounded-card bg-surface" />
      </div>
    </div>
  );
}
