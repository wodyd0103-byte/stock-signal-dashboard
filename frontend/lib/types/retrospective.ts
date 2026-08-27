/** 지난 추천이 맞았는지, 신호가 몇 번 뒤집혔는지. */

export interface RetroRecord {
  id: number;
  ticker: string;
  name?: string | null;
  market?: string | null;
  signal: string;
  buy_score: number;
  risk_score: number;
  price_at_rec: number;
  recommended_at: string;
  price_after?: number | null;
  return_pct?: number | null;
  horizon_days: number;
  hit?: number | null;
  status: string;
  evaluated_at?: string | null;
}

export interface RetroBySignal {
  signal: string;
  count: number;
  hit_rate: number;
  avg_return: number;
}

export interface RetroSummary {
  total: number;
  evaluated: number;
  open: number;
  hit_rate: number | null;
  avg_return: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  by_signal: RetroBySignal[];
  recent: RetroRecord[];
}

export interface SignalFlip {
  ticker: string;
  name: string | null;
  count: number;
}

/** 무엇이 바뀌었나. signal 만 "뒤집혔다"로 센다. */
export type SignalChangeKind = "signal" | "score" | "risk";

export interface SignalChangeRecord {
  id: number;
  kind: SignalChangeKind;
  ticker: string;
  name: string | null;
  previous_signal: string | null;
  current_signal: string;
  direction: "up" | "down" | "new";
  buy_score: number | null;
  risk_score: number | null;
  price: number | null;
  recorded_at: string;
}

/** digest CLI 가 남긴 신호 전환 이력. */
export interface SignalChangeSummary {
  days: number;
  /** 한 종목만 조회했으면 그 티커. 전체면 null. */
  ticker: string | null;
  total: number;
  tickers: number;
  flips: SignalFlip[];
  recent: SignalChangeRecord[];
}
