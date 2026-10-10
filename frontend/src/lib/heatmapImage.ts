import type { Heatmap, HeatmapLayerKey } from "@/api/types";

import { type Ramp, rampColor } from "./risk";

export interface HeatmapFrame {
  canvas: HTMLCanvasElement;
  bounds: [number, number, number, number]; // west, south, east, north
}

export function heatmapBounds(hm: Heatmap): [number, number, number, number] {
  const half = hm.step_deg / 2;
  return [
    hm.origin.lon - half,
    hm.origin.lat - half,
    hm.origin.lon + (hm.width - 1) * hm.step_deg + half,
    hm.origin.lat + (hm.height - 1) * hm.step_deg + half,
  ];
}

/** Value of one cell at a (possibly fractional) hour, linear between hourly frames. */
export function cellValue(hm: Heatmap, layer: HeatmapLayerKey, cell: number, hour: number) {
  const n = hm.cells.length / 2;
  const values = hm.layers[layer];
  const h0 = Math.max(0, Math.min(hm.hours - 1, Math.floor(hour)));
  const h1 = Math.min(hm.hours - 1, h0 + 1);
  const f = hour - h0;
  const a = values[h0 * n + cell];
  const b = values[h1 * n + cell];
  if (a == null) return f > 0 ? (b ?? null) : null;
  if (b == null || f === 0) return a;
  return a + (b - a) * f;
}

/** Output pixels per lattice cell. Upsampling lets corridor edges fade smoothly. */
export const UPSAMPLE = 4;

/** Dense grid (row 0 = south) of values at `hour`; NaN outside the corridor or without data. */
function denseGrid(hm: Heatmap, layer: HeatmapLayerKey, hour: number): Float32Array {
  const grid = new Float32Array(hm.width * hm.height).fill(Number.NaN);
  const n = hm.cells.length / 2;
  for (let c = 0; c < n; c++) {
    const v = cellValue(hm, layer, c, hour);
    if (v !== null) grid[hm.cells[2 * c + 1] * hm.width + hm.cells[2 * c]] = v;
  }
  return grid;
}

/**
 * RGBA pixels for one forecast time at UPSAMPLE x the lattice resolution.
 * Values are bilinearly interpolated using only cells that have data, and the
 * share of interpolation weight that had data becomes an alpha mask, so the
 * corridor edge fades out across a cell instead of stair-stepping.
 */
export function heatmapPixels(hm: Heatmap, layer: HeatmapLayerKey, ramp: Ramp, hour: number) {
  const { width, height } = hm;
  const k = UPSAMPLE;
  const outW = width * k;
  const outH = height * k;
  const grid = denseGrid(hm, layer, hour);
  const px = new Uint8ClampedArray(outW * outH * 4);
  const at = (x: number, y: number) =>
    x < 0 || y < 0 || x >= width || y >= height ? Number.NaN : grid[y * width + x];

  for (let v = 0; v < outH; v++) {
    const gy = height - 1 - ((v + 0.5) / k - 0.5); // canvas rows run north -> south
    const y0 = Math.floor(gy);
    const fy = gy - y0;
    for (let u = 0; u < outW; u++) {
      const gx = (u + 0.5) / k - 0.5;
      const x0 = Math.floor(gx);
      const fx = gx - x0;
      let sum = 0;
      let weight = 0;
      const corners: [number, number, number][] = [
        [x0, y0, (1 - fx) * (1 - fy)],
        [x0 + 1, y0, fx * (1 - fy)],
        [x0, y0 + 1, (1 - fx) * fy],
        [x0 + 1, y0 + 1, fx * fy],
      ];
      for (const [cx, cy, w] of corners) {
        const val = at(cx, cy);
        if (!Number.isNaN(val) && w > 0) {
          sum += val * w;
          weight += w;
        }
      }
      if (weight <= 0) continue;
      const [r, g, b, a] = rampColor(ramp, sum / weight);
      const coverage = weight; // 1 inside the corridor, fading to 0 across its edge cells
      const o = (v * outW + u) * 4;
      px[o] = r;
      px[o + 1] = g;
      px[o + 2] = b;
      px[o + 3] = a * coverage * coverage * (3 - 2 * coverage); // smoothstep
    }
  }
  return { px, width: outW, height: outH };
}

export function heatmapCanvas(hm: Heatmap, layer: HeatmapLayerKey, ramp: Ramp, hour: number) {
  const { px, width, height } = heatmapPixels(hm, layer, ramp, hour);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d")!.putImageData(new ImageData(px, width, height), 0, 0);
  return canvas;
}
