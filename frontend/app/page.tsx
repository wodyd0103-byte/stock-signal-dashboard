"use client";

import { Suspense, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BarChart3, Briefcase, FlaskConical, Settings, Sparkles } from "lucide-react";
import AnalysisView from "@/components/AnalysisView";
import ComparePanel from "@/components/ComparePanel";
import DemoBanner from "@/components/DemoBanner";
import DiscoveryRail from "@/components/DiscoveryRail";
import ICPanel from "@/components/ICPanel";
import PortfolioPanel from "@/components/PortfolioPanel";
import RetrospectivePanel from "@/components/RetrospectivePanel";
import SignalHistoryPanel from "@/components/SignalHistoryPanel";
import MiniSentiment from "@/components/MiniSentiment";
import SettingsModal from "@/components/SettingsModal";
import StockSearch from "@/components/StockSearch";
import ThemeToggle from "@/components/ThemeToggle";
import WatchlistRail, { type WatchlistRailHandle } from "@/components/WatchlistRail";
import { useAnalysis } from "@/hooks/queries";
import { useTabList } from "@/hooks/useTabList";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { addWatchlist } from "@/lib/api";
import type { Period } from "@/lib/types";

type MainTab = "analysis" | "portfolio" | "research";

const TABS: { id: MainTab; label: string; icon: typeof BarChart3 }[] = [
  { id: "analysis", label: "분석", icon: BarChart3 },
  { id: "portfolio", label: "포트폴리오", icon: Briefcase },
  { id: "research", label: "리서치", icon: FlaskConical },
];

export default function HomePage() {
  // useSearchParams는 정적 프리렌더를 클라이언트 렌더로 전환하므로 경계가 필요하다.
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <Dashboard />
    </Suspense>
  );
}

function Dashboard() {
  const initialTicker = useSearchParams().get("ticker") ?? "005930";
  const [ticker, setTicker] = useState(initialTicker.toUpperCase());
  const [period, setPeriod] = useState<Period>("1y");
  const [toast, setToast] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mainTab, setMainTab] = useState<MainTab>("analysis");
  const tabs = useTabList({
    ids: TABS.map((t) => t.id),
    active: mainTab,
    onChange: setMainTab,
    label: "화면 전환",
  });
  const watchlistRef = useRef<WatchlistRailHandle>(null);

  // 종목과 기간이 곧 요청이다. 예전에는 load()가 상태를 바꾸고 직접 fetch까지
  // 했지만, 이제 상태만 바꾸면 훅이 그에 맞는 응답을 들고 온다. 마운트 시
  // 최초 로드를 위한 이펙트도 필요 없어졌다.
  const { data: analysis, error, loading } = useAnalysis(ticker, period);

  // 백엔드가 티커를 정규화해 돌려주므로 표시에는 응답 쪽을 우선한다.
  const activeTicker = analysis?.ticker ?? ticker;

  function select(nextTicker: string, nextPeriod: Period = period) {
    setTicker(nextTicker.toUpperCase());
    setPeriod(nextPeriod);
    setMainTab("analysis");
    setToast(null);
  }

  const addToWatchlist = useAsyncAction(addWatchlist, { fallbackMessage: "관심종목 추가 실패" });

  async function handleAddWatchlist() {
    if (!analysis) return;
    const added = await addToWatchlist.run(analysis.ticker);
    if (!added) return; // 실패 메시지는 addToWatchlist.error가 들고 있다
    setToast(`${analysis.ticker} 관심종목에 추가했습니다.`);
    watchlistRef.current?.reload();
  }

  const toastMessage = toast ?? addToWatchlist.error;

  return (
    <div className="min-h-screen bg-bg">
      <DemoBanner />

      {/* 상단바 */}
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
        {/* 좁은 화면에서는 검색이 아래 줄로 내려간다. 한 줄에 다 넣으면 검색 폼의
            최소 너비 때문에 페이지 전체가 가로로 넘친다. */}
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2 text-lg font-extrabold tracking-tight text-ink shrink-0">
            <Sparkles size={20} className="text-toss" />
            <span className="hidden sm:inline">
              Quant <span className="text-toss">Insight</span>
            </span>
          </div>
          <div className="order-last min-w-0 grow basis-full lg:order-none lg:basis-0">
            <StockSearch
              defaultTicker={activeTicker}
              defaultPeriod={period}
              onSearch={select}
              loading={loading}
            />
          </div>
          <div className="ml-auto flex items-center gap-1 sm:ml-0 sm:gap-3">
            <MiniSentiment sentiment={analysis?.market_sentiment ?? null} />
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
              <DiscoveryRail onSelect={(t) => select(t)} selected={analysis?.ticker} />
            </div>
            {/* lg 에서는 높이를 고정한다. 관심 목록이 스켈레톤에서 실제 목록으로
                바뀌며 높이가 변하면, 위의 발굴 레일이 flex-1 로 그만큼 줄어들고
                두 목록의 항목이 통째로 위아래로 밀린다(데스크톱 CLS의 주범이었다).
                lg 아래에서는 레일이 본문 위에 쌓이므로 자연 높이 그대로 둔다. */}
            <div className="lg:h-[300px] lg:min-h-0">
              <WatchlistRail
                ref={watchlistRef}
                onSelect={(t) => select(t)}
                selected={analysis?.ticker}
              />
            </div>
          </aside>

          {/* 메인: 3탭 (분석/포트폴리오/리서치) */}
          <section className="min-w-0">
            {/* nav 가 아니라 tablist 다. 여긴 다른 문서로 가는 링크 묶음이 아니라
                같은 화면의 영역을 갈아끼우는 것이고, 그래서 예전에 쓰던
                `aria-current="page"` 는 의미가 맞지 않았다(그건 내비 링크용). */}
            <div
              {...tabs.tablistProps}
              className="sticky top-[64px] z-20 -mx-1 mb-4 flex gap-1 rounded-2xl border border-line bg-card/90 p-1 backdrop-blur-md"
            >
              {TABS.map((t) => {
                const active = mainTab === t.id;
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    type="button"
                    {...tabs.getTabProps(t.id)}
                    className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-sm font-bold transition ${
                      active
                        ? "bg-tossStrong text-white shadow-sm"
                        : "text-muted hover:bg-surface hover:text-ink"
                    }`}
                  >
                    <Icon size={16} />
                    {t.label}
                  </button>
                );
              })}
            </div>

            {/* 패널은 셋 다 마운트해둔다(입력값·스크롤 위치 유지). 감추는 건
                className 이 아니라 hidden 속성이라 접근성 트리에서도 빠진다. */}
            <div {...tabs.getPanelProps("analysis")} className="space-y-4">
              <AnalysisView
                analysis={analysis}
                loading={loading}
                error={error}
                period={period}
                onAddWatchlist={handleAddWatchlist}
              />
              <ComparePanel currentTicker={activeTicker} onSelect={(t) => select(t)} />
            </div>
            <div {...tabs.getPanelProps("portfolio")}>
              <PortfolioPanel onSelect={(t) => select(t)} />
            </div>
            <div {...tabs.getPanelProps("research")} className="space-y-4">
              <RetrospectivePanel />
              <SignalHistoryPanel />
              <ICPanel />
            </div>
          </section>
        </div>
      </main>

      {/* 토스트 */}
      {toastMessage ? (
        <div className="fixed bottom-5 left-1/2 z-40 -translate-x-1/2 rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-bg shadow-cardHover">
          {toastMessage}
        </div>
      ) : null}

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
