/**
 * 종목 분석 응답. 위의 도메인들을 한 덩어리로 모은 것이고, 화면에서는
 * `AnalysisView` 하나가 통째로 받는다.
 */

import type { DataSourceMetadata, PricePoint } from "./common";
import type {
  DisclosureInfo,
  Fundamental,
  LearnedSignal,
  MarketSentiment,
  NewsSentiment,
  SectorStrength,
  SupplyDemand,
} from "./market";
import type { HorizonPrediction, OptimalExit, PriceTarget } from "./prediction";
import type { IndicatorDetail, RiskResponse, SignalScore, SupportResistance } from "./signal";

export interface AnalysisResponse extends DataSourceMetadata {
  ticker: string;
  period: string;
  current_price: number;
  previous_close: number;
  change: number;
  change_rate: number;
  volume: number;
  signal: SignalScore;
  indicators: IndicatorDetail[];
  risk: RiskResponse;
  predictions: HorizonPrediction[];
  long_term_predictions?: HorizonPrediction[];
  optimal_exit?: OptimalExit | null;
  price_target?: PriceTarget | null;
  market_sentiment?: MarketSentiment | null;
  supply_demand?: SupplyDemand | null;
  news_sentiment?: NewsSentiment | null;
  sector?: SectorStrength | null;
  disclosure?: DisclosureInfo | null;
  learned_signal?: LearnedSignal | null;
  fundamental?: Fundamental | null;
  price_history: PricePoint[];
  levels: SupportResistance;
  disclaimer: string;
  last_updated: string;
}
