/* API payload types (backend serializes Decimals as strings). */

export interface Sourced<T> {
  source: "ibkr_gateway" | "local_snapshot" | null;
  stale: boolean;
  as_of?: string | null;
  data?: T | null;
}

export interface AccountSummary {
  ts?: string;
  base_currency: string;
  net_liquidation: string | null;
  total_cash: string | null;
  gross_position_value: string | null;
  buying_power: string | null;
  available_funds: string | null;
  excess_liquidity: string | null;
  init_margin: string | null;
  maint_margin: string | null;
  unrealized_pnl: string | null;
  realized_pnl: string | null;
  daily_pnl?: string | null;
  leverage: string | null;
}

export interface CashBalanceRow {
  ts: string;
  currency: string;
  cash_balance: string;
  settled_cash: string | null;
  nlv_in_ccy: string | null;
  fx_rate_to_base: string | null;
}

export interface InstrumentRef {
  conid: number;
  symbol: string;
  sec_type: string;
  currency: string;
  name: string | null;
  exchange: string | null;
}

export interface PositionRow {
  ts: string;
  instrument: InstrumentRef;
  quantity: string;
  avg_cost: string | null;
  market_price: string | null;
  market_value: string | null;
  unrealized_pnl: string | null;
  daily_pnl: string | null;
  price_quality: string;
}

export interface BalancesResponse {
  source: string | null;
  stale: boolean;
  balances: CashBalanceRow[];
}

export interface PositionsResponse {
  source: string | null;
  stale: boolean;
  positions: PositionRow[];
}
