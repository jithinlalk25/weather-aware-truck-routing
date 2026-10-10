import { describe, expect, it } from "vitest";

import type { Heatmap } from "@/api/types";

import { cellValue, heatmapBounds, heatmapPixels, UPSAMPLE } from "../heatmapImage";
import { RAMPS, rampColor } from "../risk";

const hm: Heatmap = {
  step_deg: 0.5,
  origin: { lat: 40, lon: -100 },
  width: 3,
  height: 2,
  cells: [0, 0, 1, 0, 2, 1], // (x, y) from the south-west
  start: 0,
  hours: 2,
  layers: {
    risk: [0, 2, 4, /* hour 1 */ 1, null, 4],
    wind: [], gust: [], rain: [], snow: [],
  },
  generated_at: "",
};

describe("heatmap frames", () => {
  it("covers the lattice cells with half-cell margins", () => {
    expect(heatmapBounds(hm)).toEqual([-100.25, 39.75, -98.75, 40.75]);
  });

  it("interpolates between hours and tolerates missing values", () => {
    expect(cellValue(hm, "risk", 0, 0.5)).toBeCloseTo(0.5);
    expect(cellValue(hm, "risk", 1, 0)).toBe(2);
    expect(cellValue(hm, "risk", 1, 0.5)).toBe(2); // next hour missing -> hold
  });

  it("is transparent away from the corridor and opaque at a cell centre", () => {
    const { px, width, height } = heatmapPixels(hm, "risk", RAMPS.risk, 0);
    expect([width, height]).toEqual([3 * UPSAMPLE, 2 * UPSAMPLE]);
    const alphaAt = (u: number, v: number) => px[(v * width + u) * 4 + 3];
    // Cell (0, 1) (north-west) has no data: its centre pixel is fully transparent.
    expect(alphaAt(1, 1)).toBe(0);
    // Pixels near cell (2, 1)'s centre (No Travel) use the top of the ramp.
    expect(alphaAt(2 * UPSAMPLE + 1, 1)).toBeGreaterThan(rampColor(RAMPS.risk, 3.5)[3] * 0.5);
  });
});
