import type { Interval, Place, Plan, WindMode } from "@/api/types";

import { toLocalInput } from "./format";

export const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function nextQuarterHour(): Date {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(Math.ceil((d.getMinutes() + 1) / 15) * 15);
  return d;
}

export interface FormValues {
  origin: Place | null;
  destination: Place | null;
  departureLocal: string;
  departureTouched: boolean;
  loadLb: string;
  interval: Interval;
  windMode: WindMode;
  hos: boolean;
}

export function valuesFromPlan(plan: Plan): FormValues {
  return {
    origin: plan.origin,
    destination: plan.destination,
    departureLocal: toLocalInput(new Date(plan.departure_at), plan.origin.tz),
    departureTouched: true,
    loadLb: String(plan.load_lb),
    interval: plan.interval_mi,
    windMode: plan.wind_mode,
    hos: plan.hos_enabled,
  };
}

export function defaultValues(): FormValues {
  return {
    origin: null,
    destination: null,
    departureLocal: toLocalInput(nextQuarterHour(), browserTz),
    departureTouched: false,
    loadLb: "38000",
    interval: 25,
    windMode: "sustained",
    hos: true,
  };
}
