export type LevelKey = "low" | "moderate" | "high" | "severe" | "no_travel" | "no_data";
export type RiskLevel = 0 | 1 | 2 | 3 | 4;
export type WindMode = "sustained" | "gust";
export type Interval = 10 | 25 | 50;

export interface Place {
  label: string;
  lat: number;
  lon: number;
  tz?: string;
}

export interface Checkpoint {
  i: number;
  dist_mi: number;
  share_mi: number;
  lat: number;
  lon: number;
  elapsed_s: number;
  eta: number; // epoch seconds (UTC)
  tz: string;
  confidence: "high" | "medium" | "low";
  cell: [number, number];
  level: RiskLevel | null;
  factor: string;
  levels?: { wind: RiskLevel; rain: RiskLevel; snow: RiskLevel };
  load_escalated?: boolean;
  wind_mph?: number;
  gust_mph?: number;
  rain_in_hr?: number;
  snow_in_hr?: number;
  temp_f?: number | null;
  weather_code?: number | null;
}

export interface RestStop {
  kind: "break" | "rest";
  lat: number;
  lon: number;
  dist_mi: number;
  start_elapsed_s: number;
  duration_s: number;
  tz: string;
}

/** [lon, lat, road distance m, elapsed s since departure] */
export type PathVertex = [number, number, number, number];

export interface RouteOption {
  label: string;
  rank: number;
  source: "tomtom" | "via";
  distance_mi: number;
  drive_s: number;
  total_s: number;
  traffic_delay_s: number;
  arrival_at: string;
  miles_by_level: Record<LevelKey, number>;
  avg_risk: number | null;
  path: PathVertex[];
  checkpoints: Checkpoint[];
  rest_stops: RestStop[];
}

export interface Plan {
  id: string;
  created_at: string;
  origin: Required<Place>;
  destination: Required<Place>;
  departure_at: string;
  load_lb: number;
  interval_mi: Interval;
  wind_mode: WindMode;
  hos_enabled: boolean;
  recommendation: {
    label: string;
    headline: string;
    decided_by: "no_travel" | "severe" | "high" | "no_data" | "avg_risk" | "time" | "tie" | "only";
    tradeoff: string | null;
    why_not: Record<string, string>;
    warnings: string[];
  };
  notes: string[];
  weather_meta: { source: string; lattice_step_deg: number; locations: number; tare_lb: number };
  routes: RouteOption[];
}

export type HeatmapLayerKey = "risk" | "wind" | "gust" | "rain" | "snow";

export interface Heatmap {
  step_deg: number;
  origin: { lat: number; lon: number };
  width: number;
  height: number;
  cells: number[]; // flat [x0, y0, x1, y1, ...] from the south-west corner
  start: number; // epoch seconds = departure
  hours: number;
  layers: Record<HeatmapLayerKey, (number | null)[]>; // hour-major
  generated_at: string;
}

export interface PlanRequest {
  origin: Place;
  destination: Place;
  departure_local: string; // YYYY-MM-DDTHH:mm, origin wall-clock time
  load_lb: number;
  interval_mi: Interval;
  wind_mode: WindMode;
  hos: boolean;
}
