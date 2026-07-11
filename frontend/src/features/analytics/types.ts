export interface AnalyticsTotals {
  executions: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  avg_duration_ms: number;
  errors: number;
  error_rate: number;
}

export interface FeatureStat {
  feature: string;
  executions: number;
  total_tokens: number;
  cost_usd: number;
}

export interface ModelStat {
  model: string;
  executions: number;
  total_tokens: number;
  cost_usd: number;
}

export interface TimeseriesPoint {
  date: string;
  executions: number;
  total_tokens: number;
  cost_usd: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface AnalyticsOverview {
  days: number;
  totals: AnalyticsTotals;
  by_feature: FeatureStat[];
  by_model: ModelStat[];
  timeseries: TimeseriesPoint[];
  entities: {
    workflow_runs: StatusCount[];
    documents_indexed: number;
    tasks: StatusCount[];
  };
}
