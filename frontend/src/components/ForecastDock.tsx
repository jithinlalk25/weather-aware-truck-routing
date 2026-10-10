import { Loader2, Pause, Play, Truck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Plan } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { formatLocal } from "@/lib/format";
import { RAMPS, type Ramp, rgbCss } from "@/lib/risk";
import type { TruckState } from "@/lib/timeline";

export type DockLayer = keyof typeof RAMPS;

const MAX_HOURS = 48;
const STEP = 0.25; // hours
const PLAY_HOURS_PER_SECOND = 3;

interface Props {
  plan: Plan;
  routeLabel?: string;
  hour: number;
  onHour: (h: number) => void;
  layer: DockLayer;
  onLayer: (l: DockLayer) => void;
  show: boolean;
  onShow: (s: boolean) => void;
  truck: TruckState | null;
  heatmapStatus: "pending" | "error" | "success";
  heatmapError?: string;
  onRetry: () => void;
}

export function ForecastDock(p: Props) {
  const [playing, setPlaying] = useState(false);
  const hourRef = useRef(p.hour);
  useEffect(() => {
    hourRef.current = p.hour;
  }, [p.hour]);
  const onHour = p.onHour;

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    let acc = hourRef.current >= MAX_HOURS ? 0 : hourRef.current;
    const tick = (now: number) => {
      // The first rAF timestamp can precede `last`; never step backwards.
      acc = Math.min(MAX_HOURS, acc + (Math.max(0, now - last) / 1000) * PLAY_HOURS_PER_SECOND);
      last = now;
      const snapped = Math.floor(acc / STEP) * STEP;
      if (snapped !== hourRef.current) onHour(snapped);
      if (acc >= MAX_HOURS) setPlaying(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, onHour]);

  const start = Date.parse(p.plan.departure_at) / 1000;
  const gusts = p.plan.wind_mode === "gust";
  const ramp = RAMPS[p.layer];
  const timeLabel = formatLocal(start + p.hour * 3600, p.plan.origin.tz);
  const offsetLabel = `T+${Math.floor(p.hour)}h${p.hour % 1 ? ` ${String((p.hour % 1) * 60).padStart(2, "0")}m` : ""}`;

  return (
    <div className="pointer-events-auto grid gap-2.5 rounded-xl border bg-background/95 p-3 shadow-lg backdrop-blur">
      <div className="flex items-center gap-3">
        <Button
          size="icon-sm"
          variant="outline"
          aria-label={playing ? "Pause forecast animation" : "Play forecast animation"}
          onClick={() => setPlaying((x) => !x)}
        >
          {playing ? <Pause /> : <Play />}
        </Button>
        <div className="grid flex-1 gap-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="font-medium tabular-nums">
              {offsetLabel}
              <span className="ml-1.5 font-normal text-muted-foreground">{timeLabel}</span>
            </span>
            {p.truck && p.routeLabel && (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <Truck className="size-3.5" />
                Route {p.routeLabel} · {truckStatus(p.truck)}
              </span>
            )}
          </div>
          <Slider
            thumbLabel="Forecast time after departure"
            thumbValueText={`${offsetLabel}, ${timeLabel}`}
            min={0}
            max={MAX_HOURS}
            step={STEP}
            value={[p.hour]}
            onValueChange={([h]) => {
              setPlaying(false);
              p.onHour(h);
            }}
          />
          <div className="flex justify-between text-[10px] text-muted-foreground tabular-nums">
            {[0, 12, 24, 36, 48].map((h) => (
              <span key={h}>{h === 0 ? "Departure" : `+${h}h`}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2.5">
        <div className="flex items-center gap-2">
          <Switch id="heat" checked={p.show} onCheckedChange={p.onShow} size="sm" />
          <label htmlFor="heat" className="text-xs">
            Heatmap
          </label>
        </div>
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          spacing={0}
          value={p.layer}
          onValueChange={(v) => v && p.onLayer(v as DockLayer)}
          disabled={!p.show}
          aria-label="Heatmap layer"
        >
          {(Object.keys(RAMPS) as DockLayer[]).map((k) => (
            <ToggleGroupItem key={k} value={k} className="px-2.5 text-xs">
              {k === "wind" && gusts ? "Gusts" : RAMPS[k].label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="min-w-56 flex-1">
          {p.heatmapStatus === "pending" && p.show ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Loading corridor forecast…
            </span>
          ) : p.heatmapStatus === "error" && p.show ? (
            <span className="text-xs text-destructive">
              {p.heatmapError ?? "Heatmap unavailable."}{" "}
              <button className="underline" onClick={p.onRetry}>
                Retry
              </button>
            </span>
          ) : (
            <Legend ramp={ramp} />
          )}
        </div>
      </div>
      <MarkerKey />
    </div>
  );
}

function MarkerKey() {
  const dot = (fill: string, stroke: string) => (
    <span className="size-2.5 rounded-full border-2" style={{ background: fill, borderColor: stroke }} />
  );
  return (
    <div className="hidden flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground sm:flex">
      <span className="inline-flex items-center gap-1">{dot("#2563eb", "#fff")} Truck at slider time</span>
      <span className="inline-flex items-center gap-1">{dot("#475569", "#fff")} 10-h HOS rest</span>
      <span className="inline-flex items-center gap-1">{dot("#fff", "#475569")} 30-min break</span>
      <span className="inline-flex items-center gap-1">{dot("#fff", "#0f172a")} Origin</span>
      <span className="inline-flex items-center gap-1">{dot("#0f172a", "#0f172a")} Destination</span>
    </div>
  );
}

function truckStatus(t: TruckState): string {
  if (t.status === "arrived") return "arrived";
  const where = `mile ${t.distMi.toFixed(0)}`;
  if (t.status === "rest") return `${where} · 10-h rest`;
  if (t.status === "break") return `${where} · 30-min break`;
  return `${where} · driving`;
}

function Legend({ ramp }: { ramp: Ramp }) {
  const min = ramp.stops[0].at;
  const max = ramp.stops[ramp.stops.length - 1].at;
  const pos = (v: number) => ((v - min) / (max - min)) * 100;
  if (ramp.key === "risk") {
    return (
      <div className="flex flex-wrap gap-x-2.5 gap-y-1 text-[11px]">
        {ramp.ticks.map((t, i) => (
          <span key={t.label} className="inline-flex items-center gap-1">
            <span className="size-2.5 rounded-sm" style={{ background: rgbCss(ramp.stops[i].rgb, 0.85) }} />
            {t.label}
          </span>
        ))}
      </div>
    );
  }
  const gradient = ramp.stops
    .map((s) => `${rgbCss(s.rgb, Math.max(s.alpha, 0.08))} ${pos(s.at)}%`)
    .join(", ");
  return (
    <div className="flex items-start gap-2">
      <div className="grid flex-1 gap-0.5">
        <div className="h-2 rounded-full" style={{ background: `linear-gradient(90deg, ${gradient})` }} />
        <div className="relative h-3 text-[10px] text-muted-foreground tabular-nums">
          {ramp.ticks.map((t) => (
            <span key={t.at} className="absolute -translate-x-1/2" style={{ left: `${pos(t.at)}%` }}>
              {t.label}
            </span>
          ))}
        </div>
      </div>
      <span className="-mt-0.5 text-[10px] whitespace-nowrap text-muted-foreground">{ramp.unit}</span>
    </div>
  );
}
