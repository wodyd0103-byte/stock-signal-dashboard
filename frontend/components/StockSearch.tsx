"use client";

import { FormEvent, KeyboardEvent, useId, useState } from "react";
import { Search } from "lucide-react";
import { useTickerUniverse } from "@/hooks/queries";
import { periods } from "@/lib/api";
import { matchTickers } from "@/lib/tickerSearch";
import type { Period, RepresentativeStock } from "@/lib/types";

interface StockSearchProps {
  defaultTicker?: string;
  defaultPeriod?: Period;
  onSearch: (ticker: string, period: Period) => void;
  loading?: boolean;
}

export default function StockSearch({
  defaultTicker = "AAPL",
  defaultPeriod = "1y",
  onSearch,
  loading,
}: StockSearchProps) {
  const [ticker, setTicker] = useState(defaultTicker);
  const [period, setPeriod] = useState<Period>(defaultPeriod);

  // 부모가 다른 종목/기간을 확정하면 입력값도 따라가야 한다. 이펙트로 맞추면 한 번 더
  // 렌더된 뒤에 값이 바뀌므로, React가 권장하는 렌더 중 조정 방식을 쓴다.
  // https://react.dev/reference/react/useState#storing-information-from-previous-renders
  const [syncedTicker, setSyncedTicker] = useState(defaultTicker);
  if (syncedTicker !== defaultTicker) {
    setSyncedTicker(defaultTicker);
    setTicker(defaultTicker);
  }

  const [syncedPeriod, setSyncedPeriod] = useState<Period>(defaultPeriod);
  if (syncedPeriod !== defaultPeriod) {
    setSyncedPeriod(defaultPeriod);
    setPeriod(defaultPeriod);
  }

  // 종목 목록은 검색을 처음 건드릴 때 받는다. 한 번도 안 쓰는 방문자에게는
  // 요청이 나가지 않고, 받은 뒤로는 훅이 들고 있어 다시 부르지 않는다.
  const [touched, setTouched] = useState(false);
  const universe = useTickerUniverse(touched);

  const [open, setOpen] = useState(false);
  // -1 = 아무것도 고르지 않음. 화살표로 내려야 후보가 잡힌다. 첫 후보를 미리
  // 잡아두면 "AAP" 를 치고 Enter 친 사람에게 AAPL 을 보내게 되는데, 이 폼은
  // 원래 친 그대로 보내는 계약이었고 유니버스에 없는 종목도 조회가 된다.
  const [activeIndex, setActiveIndex] = useState(-1);

  const suggestions = open ? matchTickers(universe.data ?? [], ticker) : [];

  // 입력이 바뀌면 강조 위치를 처음으로 되돌린다. 이펙트로 하면 한 프레임 동안
  // 옛 위치가 남아 Enter가 엉뚱한 종목을 고른다.
  const [syncedQuery, setSyncedQuery] = useState(ticker);
  if (syncedQuery !== ticker) {
    setSyncedQuery(ticker);
    setActiveIndex(-1);
  }

  const listboxId = useId();
  const optionId = (index: number) => `${listboxId}-option-${index}`;

  function run(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    setOpen(false);
    onSearch(trimmed.toUpperCase(), period);
  }

  function choose(stock: RepresentativeStock) {
    setTicker(stock.ticker);
    setSyncedQuery(stock.ticker);
    run(stock.ticker);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // 후보를 고르는 중이면 그것을, 아니면 친 그대로 보낸다. 유니버스에 없는
    // 종목도 백엔드는 조회할 수 있으므로 입력을 후보로 가둬서는 안 된다.
    const active = activeIndex >= 0 ? suggestions[activeIndex] : undefined;
    if (active) choose(active);
    else run(ticker);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!suggestions.length) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      // -1 에서 위로 가면 마지막 후보. (-1 - 1 + n) % n 은 그 값이 안 나온다.
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
    }
  }

  return (
    // 좁은 화면에서는 입력이 한 줄을 다 쓰고, 기간 선택과 분석 버튼이 아랫줄로 내려간다.
    <form onSubmit={handleSubmit} className="card flex flex-wrap items-center gap-2.5 p-2.5">
      <div className="relative flex min-w-0 grow basis-full items-center gap-2 rounded-xl bg-surface px-4 transition-all focus-within:bg-bg focus-within:ring-2 focus-within:ring-toss/50 sm:basis-0">
        <Search size={18} className="text-muted shrink-0" />
        <input
          value={ticker}
          onChange={(event) => {
            setTicker(event.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setTouched(true);
            setOpen(true);
          }}
          // 후보를 마우스로 고를 때 blur가 먼저 닫아버리지 않도록 목록 쪽에서
          // mousedown 기본동작을 막는다. 여기서는 그냥 닫으면 된다.
          onBlur={() => setOpen(false)}
          onKeyDown={handleKeyDown}
          className="h-12 flex-1 bg-transparent text-base font-semibold text-ink placeholder:text-faint placeholder:font-normal outline-none"
          placeholder="종목명 또는 티커 검색  (AAPL, 005930, 삼성전자)"
          role="combobox"
          aria-expanded={suggestions.length > 0}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? optionId(activeIndex) : undefined}
          autoComplete="off"
        />

        {suggestions.length > 0 ? (
          <ul
            id={listboxId}
            role="listbox"
            aria-label="종목 검색 결과"
            className="absolute left-0 right-0 top-full z-40 mt-1.5 overflow-hidden rounded-xl border border-line bg-bg py-1 shadow-card"
          >
            {suggestions.map((stock, index) => (
              <li
                key={stock.ticker}
                id={optionId(index)}
                role="option"
                aria-selected={index === activeIndex}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => choose(stock)}
                className={`flex cursor-pointer items-center justify-between gap-3 px-4 py-2.5 text-sm ${
                  index === activeIndex ? "bg-surface" : ""
                }`}
              >
                <span className="min-w-0 truncate font-bold text-ink">{stock.name}</span>
                <span className="shrink-0 text-xs font-medium text-muted tabular">
                  {stock.ticker} · {stock.market}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="flex h-12 min-w-0 grow items-center rounded-xl bg-surface p-1 sm:grow-0">
        {periods.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setPeriod(item.value)}
            className={`h-10 grow rounded-lg px-2 text-sm font-bold transition-colors sm:grow-0 sm:px-3 ${
              period === item.value ? "bg-bg text-ink shadow-card" : "text-muted hover:text-sub"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="inline-flex h-12 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-toss px-4 text-base font-bold text-white transition-colors hover:bg-toss-600 disabled:cursor-not-allowed disabled:bg-toss-300 sm:min-w-28 sm:px-5"
      >
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          <Search size={18} />
        )}
        분석
      </button>
    </form>
  );
}
