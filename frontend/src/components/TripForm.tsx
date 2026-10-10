import { ArrowDownUp, Loader2, Route } from "lucide-react";
import { type FormEvent, useState } from "react";

import { ApiError } from "@/api/client";
import type { Interval, Place, PlanRequest } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { toLocalInput, tzAbbrev } from "@/lib/format";
import { browserTz, type FormValues, nextQuarterHour } from "@/lib/formValues";

import { PlaceAutocomplete } from "./PlaceAutocomplete";

const EXAMPLES: { name: string; origin: Place; destination: Place }[] = [
  {
    name: "Chicago → Denver",
    origin: { label: "Chicago, IL", lat: 41.8781, lon: -87.6298, tz: "America/Chicago" },
    destination: { label: "Denver, CO", lat: 39.7392, lon: -104.9903, tz: "America/Denver" },
  },
  {
    name: "Seattle → Salt Lake City",
    origin: { label: "Seattle, WA", lat: 47.6062, lon: -122.3321, tz: "America/Los_Angeles" },
    destination: { label: "Salt Lake City, UT", lat: 40.7608, lon: -111.891, tz: "America/Denver" },
  },
  {
    name: "Dallas → Atlanta",
    origin: { label: "Dallas, TX", lat: 32.7767, lon: -96.797, tz: "America/Chicago" },
    destination: { label: "Atlanta, GA", lat: 33.749, lon: -84.388, tz: "America/New_York" },
  },
];

interface Props {
  /** Read once on mount; give the form a new `key` to reset it. */
  initial: FormValues;
  pending: boolean;
  error: Error | null;
  /** When a plan is on screen, option toggles re-plan immediately. */
  autoApplyOptions: boolean;
  onSubmit: (req: PlanRequest) => void;
}

export function TripForm({ initial, pending, error, autoApplyOptions, onSubmit }: Props) {
  const [v, setV] = useState<FormValues>(initial);
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({});
  const [now] = useState(() => Date.now());

  const tz = v.origin?.tz ?? browserTz;
  const min = toLocalInput(new Date(now), tz);
  const max = toLocalInput(new Date(now + 7 * 86400_000), tz);

  // Until the user picks a time, keep "departure" at the next quarter hour in the origin's zone.
  const setOrigin = (origin: Place | null) =>
    setV((s) => ({
      ...s,
      origin,
      departureLocal:
        s.departureTouched || !origin?.tz
          ? s.departureLocal
          : toLocalInput(nextQuarterHour(), origin.tz),
    }));

  const fieldErrors = { ...(error instanceof ApiError ? flat(error.fields) : {}), ...localErrors };

  const build = (s: FormValues): PlanRequest | null => {
    const errs: Record<string, string> = {};
    if (!s.origin) errs.origin = "Choose an origin from the list.";
    if (!s.destination) errs.destination = "Choose a destination from the list.";
    const load = Number(s.loadLb);
    if (!Number.isFinite(load) || load < 0 || load > 80_000)
      errs.load_lb = "Enter a load between 0 and 80,000 lb.";
    if (!s.departureLocal) errs.departure_local = "Choose a departure time.";
    setLocalErrors(errs);
    if (Object.keys(errs).length) return null;
    return {
      origin: s.origin!,
      destination: s.destination!,
      departure_local: s.departureLocal,
      load_lb: Math.round(load),
      interval_mi: s.interval,
      wind_mode: s.windMode,
      hos: s.hos,
    };
  };

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const req = build(v);
    if (req) onSubmit(req);
  };

  const setOption = (patch: Partial<FormValues>) => {
    const next = { ...v, ...patch };
    setV(next);
    if (autoApplyOptions && !pending) {
      const req = build(next);
      if (req) onSubmit(req);
    }
  };

  const generalError =
    error && !(error instanceof ApiError && Object.keys(error.fields).length) ? error.message : null;

  return (
    <form onSubmit={submit} className="grid gap-4" noValidate>
      <div className="grid gap-3">
        <PlaceAutocomplete
          label="Origin"
          value={v.origin}
          onChange={setOrigin}
          placeholder="City or address"
          error={fieldErrors.origin}
        />
        <div className="relative">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Swap origin and destination"
            className="absolute -top-2.5 right-1 z-10 text-muted-foreground"
            onClick={() =>
              setV((s) => ({
                ...s,
                origin: s.destination,
                destination: s.origin,
                departureLocal:
                  s.departureTouched || !s.destination?.tz
                    ? s.departureLocal
                    : toLocalInput(nextQuarterHour(), s.destination.tz),
              }))
            }
          >
            <ArrowDownUp />
          </Button>
          <PlaceAutocomplete
            label="Destination"
            value={v.destination}
            onChange={(destination) => setV((s) => ({ ...s, destination }))}
            placeholder="City or address"
            error={fieldErrors.destination}
          />
        </div>
        {!v.origin && !v.destination && (
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.name}
                type="button"
                className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                onClick={() =>
                  setV((s) => ({
                    ...s,
                    origin: ex.origin,
                    destination: ex.destination,
                    departureLocal: s.departureTouched
                      ? s.departureLocal
                      : toLocalInput(nextQuarterHour(), ex.origin.tz!),
                  }))
                }
              >
                {ex.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-[1fr_8.5rem] gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="departure" className="text-xs text-muted-foreground">
            {v.origin?.tz ? `Departure (${tzAbbrev(tz)}, origin time)` : "Departure (origin local time)"}
          </Label>
          <Input
            id="departure"
            type="datetime-local"
            value={v.departureLocal}
            min={min}
            max={max}
            step={900}
            aria-invalid={!!fieldErrors.departure_local}
            onChange={(e) =>
              setV((s) => ({ ...s, departureLocal: e.target.value, departureTouched: true }))
            }
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="load" className="text-xs text-muted-foreground">
            Load weight (lb)
          </Label>
          <Input
            id="load"
            inputMode="numeric"
            value={v.loadLb}
            aria-invalid={!!fieldErrors.load_lb}
            onChange={(e) => setV((s) => ({ ...s, loadLb: e.target.value.replace(/[^\d]/g, "") }))}
          />
        </div>
      </div>
      {(fieldErrors.departure_local || fieldErrors.load_lb) && (
        <p className="-mt-2 text-xs text-destructive">
          {fieldErrors.departure_local ?? fieldErrors.load_lb}
        </p>
      )}

      <div className="grid gap-3 rounded-lg border bg-muted/30 p-3">
        <div className="flex items-center justify-between gap-3">
          <Label className="text-xs text-muted-foreground">Weather checkpoint every</Label>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            spacing={0}
            value={String(v.interval)}
            onValueChange={(x) => x && setOption({ interval: Number(x) as Interval })}
          >
            {[10, 25, 50].map((mi) => (
              <ToggleGroupItem key={mi} value={String(mi)} className="px-2.5 text-xs">
                {mi} mi
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <OptionSwitch
          id="gusts"
          label="Conservative mode"
          hint="Classify wind on gusts instead of sustained speed"
          checked={v.windMode === "gust"}
          onChange={(c) => setOption({ windMode: c ? "gust" : "sustained" })}
        />
        <OptionSwitch
          id="hos"
          label="Hours-of-Service stops"
          hint="30-min break after 8 h driving, 10 h rest after 11 h"
          checked={v.hos}
          onChange={(c) => setOption({ hos: c })}
        />
      </div>

      {generalError && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {generalError}
        </p>
      )}

      <Button type="submit" disabled={pending} className="w-full">
        {pending ? <Loader2 className="animate-spin" /> : <Route />}
        {pending ? "Planning routes…" : "Plan routes"}
      </Button>
    </form>
  );
}

function OptionSwitch(props: {
  id: string;
  label: string;
  hint: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Label htmlFor={props.id} className="grid gap-0.5 font-normal">
        <span className="text-sm">{props.label}</span>
        <span className="text-xs text-muted-foreground">{props.hint}</span>
      </Label>
      <Switch id={props.id} checked={props.checked} onCheckedChange={props.onChange} />
    </div>
  );
}

function flat(fields: Record<string, string[]>): Record<string, string> {
  return Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, v[0]]));
}
