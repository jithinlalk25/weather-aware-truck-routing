import type { Checkpoint, PathVertex, RestStop, RiskLevel } from "@/api/types";

export interface TruckState {
  lon: number;
  lat: number;
  distMi: number;
  status: "driving" | "break" | "rest" | "arrived";
}

const METERS_PER_MILE = 1609.344;

/** Truck position `elapsedS` seconds after departure, interpolated along the timed path. */
export function truckAt(path: PathVertex[], stops: RestStop[], elapsedS: number): TruckState {
  const last = path[path.length - 1];
  if (elapsedS >= last[3]) {
    return { lon: last[0], lat: last[1], distMi: last[2] / METERS_PER_MILE, status: "arrived" };
  }
  let lo = 0;
  let hi = path.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (path[mid][3] <= elapsedS) lo = mid;
    else hi = mid;
  }
  const a = path[lo];
  const b = path[hi];
  const span = b[3] - a[3];
  const t = span > 0 ? (elapsedS - a[3]) / span : 0;
  const stop = stops.find(
    (s) => elapsedS >= s.start_elapsed_s && elapsedS < s.start_elapsed_s + s.duration_s,
  );
  return {
    lon: a[0] + (b[0] - a[0]) * t,
    lat: a[1] + (b[1] - a[1]) * t,
    distMi: (a[2] + (b[2] - a[2]) * t) / METERS_PER_MILE,
    status: stop ? stop.kind : "driving",
  };
}

export interface RiskRun {
  level: RiskLevel | null;
  path: [number, number][];
}

/**
 * Split a route into runs of constant risk. Each checkpoint owns the road
 * between the midpoints to its neighbours (matching the backend's mileage), and
 * run boundaries are interpolated to the exact midpoint distance.
 */
export function riskRuns(path: PathVertex[], checkpoints: Checkpoint[]): RiskRun[] {
  if (path.length < 2 || checkpoints.length === 0) return [];
  const bounds = checkpoints.map((c, i) =>
    i === checkpoints.length - 1
      ? Infinity
      : ((c.dist_mi + checkpoints[i + 1].dist_mi) / 2) * METERS_PER_MILE,
  );
  const runs: RiskRun[] = [];
  let k = 0;
  let current: RiskRun = { level: checkpoints[0].level, path: [[path[0][0], path[0][1]]] };
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    while (k < checkpoints.length - 1 && b[2] > bounds[k]) {
      const span = b[2] - a[2];
      const t = span > 0 ? Math.min(Math.max((bounds[k] - a[2]) / span, 0), 1) : 1;
      const p: [number, number] = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
      k++;
      if (checkpoints[k].level !== current.level) {
        current.path.push(p);
        runs.push(current);
        current = { level: checkpoints[k].level, path: [p] };
      }
    }
    current.path.push([b[0], b[1]]);
  }
  runs.push(current);
  return runs.filter((r) => r.path.length > 1);
}
