import type { HeatmapLayerKey, LevelKey, RiskLevel } from "@/api/types";

export type RGB = [number, number, number];

export const LEVELS: { key: LevelKey; label: string; rgb: RGB }[] = [
  { key: "low", label: "Low", rgb: [22, 163, 74] },
  { key: "moderate", label: "Moderate", rgb: [234, 179, 8] },
  { key: "high", label: "High", rgb: [249, 115, 22] },
  { key: "severe", label: "Severe", rgb: [220, 38, 38] },
  { key: "no_travel", label: "No Travel", rgb: [126, 34, 206] },
];
export const NO_DATA = { key: "no_data" as const, label: "No data", rgb: [156, 163, 175] as RGB };

export function levelInfo(level: RiskLevel | null) {
  return level === null ? NO_DATA : LEVELS[level];
}

export const rgbCss = ([r, g, b]: RGB, a = 1) => `rgba(${r}, ${g}, ${b}, ${a})`;

interface Stop {
  at: number;
  rgb: RGB;
  alpha: number;
}

export interface Ramp {
  key: HeatmapLayerKey;
  label: string;
  unit: string;
  stops: Stop[];
  ticks: { at: number; label: string }[];
}

/** Continuous color ramps for heatmap layers. Risk follows the level colors. */
export const RAMPS: Record<"risk" | "wind" | "rain" | "snow", Ramp> = {
  risk: {
    key: "risk",
    label: "Risk",
    unit: "",
    stops: LEVELS.map((l, i) => ({ at: i, rgb: l.rgb, alpha: [0.22, 0.45, 0.58, 0.68, 0.78][i] })),
    ticks: LEVELS.map((l, i) => ({ at: i, label: l.label })),
  },
  wind: {
    key: "wind",
    label: "Wind",
    unit: "mph",
    stops: [
      { at: 0, rgb: [56, 189, 248], alpha: 0 },
      { at: 15, rgb: [56, 189, 248], alpha: 0.3 },
      { at: 25, rgb: [234, 179, 8], alpha: 0.45 }, // Moderate
      { at: 35, rgb: [249, 115, 22], alpha: 0.55 }, // High
      { at: 45, rgb: [220, 38, 38], alpha: 0.65 }, // Severe
      { at: 55, rgb: [126, 34, 206], alpha: 0.75 }, // No Travel
    ],
    ticks: [0, 25, 35, 45, 55].map((v) => ({ at: v, label: `${v}` })),
  },
  rain: {
    key: "rain",
    label: "Rain",
    unit: "in/hr",
    stops: [
      { at: 0, rgb: [96, 165, 250], alpha: 0 },
      { at: 0.02, rgb: [96, 165, 250], alpha: 0.25 },
      { at: 0.1, rgb: [59, 130, 246], alpha: 0.45 },
      { at: 0.25, rgb: [37, 99, 235], alpha: 0.6 },
      { at: 0.5, rgb: [30, 64, 175], alpha: 0.7 },
      { at: 1, rgb: [126, 34, 206], alpha: 0.8 },
    ],
    ticks: [0, 0.1, 0.25, 0.5, 1].map((v) => ({ at: v, label: `${v}` })),
  },
  snow: {
    key: "snow",
    label: "Snow",
    unit: "in/hr",
    stops: [
      { at: 0, rgb: [165, 243, 252], alpha: 0 },
      { at: 0.05, rgb: [165, 243, 252], alpha: 0.3 },
      { at: 0.5, rgb: [103, 232, 249], alpha: 0.5 },
      { at: 1, rgb: [129, 140, 248], alpha: 0.6 },
      { at: 2, rgb: [139, 92, 246], alpha: 0.7 },
      { at: 3, rgb: [126, 34, 206], alpha: 0.8 },
    ],
    ticks: [0, 0.5, 1, 2, 3].map((v) => ({ at: v, label: `${v}` })),
  },
};

/** RGBA (0-255) for a value on a ramp; linear between stops, clamped at the ends. */
export function rampColor(ramp: Ramp, value: number): [number, number, number, number] {
  const s = ramp.stops;
  if (value <= s[0].at) return [...s[0].rgb, Math.round(s[0].alpha * 255)];
  for (let i = 1; i < s.length; i++) {
    if (value <= s[i].at) {
      const t = (value - s[i - 1].at) / (s[i].at - s[i - 1].at);
      const mix = (a: number, b: number) => a + (b - a) * t;
      return [
        Math.round(mix(s[i - 1].rgb[0], s[i].rgb[0])),
        Math.round(mix(s[i - 1].rgb[1], s[i].rgb[1])),
        Math.round(mix(s[i - 1].rgb[2], s[i].rgb[2])),
        Math.round(mix(s[i - 1].alpha, s[i].alpha) * 255),
      ];
    }
  }
  const last = s[s.length - 1];
  return [...last.rgb, Math.round(last.alpha * 255)];
}
