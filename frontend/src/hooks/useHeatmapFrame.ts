import { useMemo } from "react";

import type { Heatmap, HeatmapLayerKey } from "@/api/types";
import { type HeatmapFrame, heatmapBounds, heatmapCanvas } from "@/lib/heatmapImage";
import type { Ramp } from "@/lib/risk";

// Frames per heatmap payload; dropped automatically when the payload is.
const frames = new WeakMap<Heatmap, Map<string, HTMLCanvasElement>>();

function frameFor(hm: Heatmap, layer: HeatmapLayerKey, ramp: Ramp, hour: number) {
  let cache = frames.get(hm);
  if (!cache) frames.set(hm, (cache = new Map()));
  const key = `${layer}:${hour}`;
  let canvas = cache.get(key);
  if (!canvas) cache.set(key, (canvas = heatmapCanvas(hm, layer, ramp, hour)));
  return canvas;
}

/**
 * Canvas for the current slider position. Frames are tiny (one pixel per
 * lattice cell) and memoised, so scrubbing only swaps a texture.
 */
export function useHeatmapFrame(
  hm: Heatmap | undefined,
  layer: HeatmapLayerKey,
  ramp: Ramp,
  hour: number,
  enabled: boolean,
): HeatmapFrame | null {
  const bounds = useMemo(() => (hm ? heatmapBounds(hm) : null), [hm]);
  return useMemo(
    () =>
      hm && bounds && enabled ? { canvas: frameFor(hm, layer, ramp, hour), bounds } : null,
    [hm, bounds, layer, ramp, hour, enabled],
  );
}
