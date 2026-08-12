"use client";

import { useEffect, useRef, useState } from "react";
import { BarChart3, Briefcase, FlaskConical, Settings, Sparkles } from "lucide-react";
import AnalysisView from "@/components/AnalysisView";
import ComparePanel from "@/components/ComparePanel";
import DiscoveryRail from "@/components/DiscoveryRail";
import ICPanel from "@/components/ICPanel";
import PortfolioPanel from "@/components/PortfolioPanel";
import RetrospectivePanel from "@/components/RetrospectivePanel";
import MiniSentiment from "@/components/MiniSentiment";
import SettingsModal from "@/components/SettingsModal";
import StockSearch from "@/components/StockSearch";
import ThemeToggle from "@/components/ThemeToggle";
import WatchlistRail, { type WatchlistRailHandle } from "@/components/WatchlistRail";
import { addWatchlist, fetchAnalysis } from "@/lib/api";
import type { AnalysisResponse, MarketSentiment, Period } from "@/lib/types";

type MainTab = "analysis" | "portfolio" | "research";

const TABS: { id: MainTab; label: string; icon: typeof BarChart3 }[] = [
  { id: "analysis", label: "분석", icon: BarChart3 },
  { id: "portfolio", label: "포트폴리오", icon: Briefcase },
  { id: "research", label: "리서치", icon: FlaskConical },
];

export default function HomePage() {
  const [ticker, setTicker] = useState("005930");
  const [period, setPeriod] = useState<Period>("1y");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sentiment, setSentiment] = useState<MarketSentiment | null>(null);
  const [mainTab, setMainTab] = useState<MainTab>("analysis");
  const watchlistRef = useRef<WatchlistRailHandle>(null);

  async function load(nextTicker = ticker, nextPeriod = period) {
    setLoading(true);
    setToast(null);
    setMainTab("analysis");
    setTicker(nextTicker.toUpperCase());
    setPeriod(nextPeriod);
    try {
      const data = await fetchAnalysis(nextTicker, nextPeriod);
      setAnalysis(data);
      setTicker(data.ticker);
      if (data.market_sentiment) setSentiment(data.market_sentiment);
    } catch (e) {
      setToast(e instanceof Error ? e.message : "분석 데이터를 불러오지 못했습니다.");
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleAddWatchlist() {
    if (!analysis) return;
    try {
      await addWatchlist(analysis.ticker);
      setToast(`${analysis.ticker} 관심종목에 추가했습니다.`);
      watchlistRef.current?.reload();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "관심종목 추가 실패");
    }
  }

  // 마운트 시 최초 분석. load()가 동기적으로 setLoading(true)를 호출하기 때문에
  // set-state-in-effect에 걸린다. 데이터 페칭을 TanStack Query로 옮기면 이 이펙트
  // 자체가 사라지므로, 그때까지만 억제한다.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(params.get("ticker") ?? "005930", "1y");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-bg">
      {/* 상단바 */}
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
        {/* 좁은 화면에서는 검색이 아래 줄로 내려간다. 한 줄에 다 넣으면 검색 폼의
            최소 너비 때문에 페이지 전체가 가로로 넘친다. */}
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2 text-lg font-extrabold tracking-tight text-ink shrink-0">
            <Sparkles size={20} className="text-toss" />
            <span className="hidden sm:inline">Quant <span className="text-toss">Insight</span></span>
          </div>
          <div className="order-last min-w-0 grow basis-full lg:order-none lg:basis-0">
            <StockSearch
              defaultTicker={ticker}
              defaultPeriod={period}
              onSearch={(t, p) => void load(t, p)}
              loading={loading}
            />
          </div>
          <div className="ml-auto flex items-center gap-1 sm:ml-0 sm:gap-3">
            <MiniSentiment sentiment={sentiment} />
            <ThemeToggle />
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="rounded-xl p-2.5 text-muted hover:bg-surface hover:text-ink"
              aria-label="설정"
            >
              <Settings size={18} />
            </button>
          </div>
        </div>
      </header>

      {/* 본문: 좌측 레일 + 메인 */}
      <main className="mx-auto max-w-[1600px] px-4 py-4">
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          {/* 좌측 레일 */}
          <aside className="flex flex-col gap-4 lg:sticky lg:top-[72px] lg:h-[calc(100vh-88px)]">
            <div className="min-h-0 flex-1">
              <DiscoveryRail onSelect={(t) => void load(t, period)} selected={analysis?.ticker} />
            </div>
            <WatchlistRail ref={watchlistRef} onSelect={(t) => void load(t, period)} selected={analysis?.ticker} />
          </aside>

          {/* 메인: 3탭 (분석/포트폴리오/리서치) */}
          <section className="min-w-0">
            <nav className="sticky top-[64px] z-20 -mx-1 mb-4 flex gap-1 rounded-2xl border border-line bg-card/90 p-1 backdrop-blur-md">
              {TABS.map((t) => {
                const active = mainTab === t.id;
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setMainTab(t.id)}
                    className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-sm font-bold transition ${
                      active ? "bg-toss text-white shadow-sm" : "text-muted hover:bg-surface hover:text-ink"
                    }`}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon size={16} />
                    {t.label}
                  </button>
                );
              })}
            </nav>

            <div className={mainTab === "analysis" ? "space-y-4" : "hidden"}>
              <AnalysisView
                analysis={analysis}
                loading={loading}
                period={period}
                onAddWatchlist={handleAddWatchlist}
              />
              <ComparePanel currentTicker={ticker} onSelect={(t) => void load(t, period)} />
            </div>
            <div className={mainTab === "portfolio" ? "" : "hidden"}>
              <PortfolioPanel onSelect={(t) => void load(t, period)} />
            </div>
            <div className={mainTab === "research" ? "space-y-4" : "hidden"}>
              <RetrospectivePanel />
              <ICPanel />
            </div>
          </section>
        </div>
      </main>

      {/* 토스트 */}
      {toast ? (
        <div className="fixed bottom-5 left-1/2 z-40 -translate-x-1/2 rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-bg shadow-cardHover">
          {toast}
        </div>
      ) : null}

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
