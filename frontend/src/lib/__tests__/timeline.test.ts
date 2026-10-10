import { describe, expect, it } from "vitest";

import type { Checkpoint, PathVertex, RestStop } from "@/api/types";

import { riskRuns, truckAt } from "../timeline";

const MI = 1609.344;

// 0 -> 100 mi due east, driving 1 mi/min, with a 30-min break at mile 50.
const path: PathVertex[] = [
  [0, 0, 0, 0],
  [1, 0, 50 * MI, 3000],
  [1, 0, 50 * MI, 4800],
  [2, 0, 100 * MI, 7800],
];
const stops: RestStop[] = [
  { kind: "break", lat: 0, lon: 1, dist_mi: 50, start_elapsed_s: 3000, duration_s: 1800, tz: "UTC" },
];

function cp(i: number, dist_mi: number, level: Checkpoint["level"]): Checkpoint {
  return {
    i, dist_mi, share_mi: 0, lat: 0, lon: 0, elapsed_s: 0, eta: 0, tz: "UTC",
    confidence: "high", cell: [0, 0], level, factor: "",
  };
}

describe("truckAt", () => {
  it("interpolates while driving", () => {
    const t = truckAt(path, stops, 1500);
    expect(t.lon).toBeCloseTo(0.5);
    expect(t.distMi).toBeCloseTo(25);
    expect(t.status).toBe("driving");
  });

  it("holds position during an HOS break", () => {
    const t = truckAt(path, stops, 4000);
    expect(t.lon).toBeCloseTo(1);
    expect(t.status).toBe("break");
  });

  it("reports arrival after the last vertex", () => {
    expect(truckAt(path, stops, 99_999).status).toBe("arrived");
  });
});

describe("riskRuns", () => {
  it("splits at the midpoint between checkpoints with different levels", () => {
    const runs = riskRuns(path, [cp(0, 0, 0), cp(1, 40, 0), cp(2, 80, 3), cp(3, 100, 3)]);
    expect(runs.map((r) => r.level)).toEqual([0, 3]);
    // Boundary at mile 60 = lon 1.2 on the second leg.
    expect(runs[0].path.at(-1)![0]).toBeCloseTo(1.2);
    expect(runs[1].path[0][0]).toBeCloseTo(1.2);
  });

  it("merges consecutive checkpoints with the same level", () => {
    const runs = riskRuns(path, [cp(0, 0, 1), cp(1, 50, 1), cp(2, 100, 1)]);
    expect(runs).toHaveLength(1);
    expect(runs[0].path.at(-1)).toEqual([2, 0]);
  });
});
