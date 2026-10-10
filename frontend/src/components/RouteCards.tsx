import { AlertTriangle, CheckCircle2, Clock, Info } from "lucide-react";
import { memo } from "react";

import type { Plan, RouteOption } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { formatDuration, formatLocal, formatMiles } from "@/lib/format";
import { LEVELS, NO_DATA, rgbCss } from "@/lib/risk";
import { cn } from "@/lib/utils";

import { RiskStrip } from "./RiskStrip";

export const RecommendationCard = memo(function RecommendationCard({ plan }: { plan: Plan }) {
  const rec = plan.recommendation;
  const danger = plan.routes.every((r) => r.miles_by_level.no_travel > 0);
  return (
    <section className="grid gap-2">
      <div
        className={cn(
          "rounded-lg border p-3",
          danger ? "border-destructive/40 bg-destructive/5" : "border-emerald-600/30 bg-emerald-50",
        )}
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          {danger ? (
            <AlertTriangle className="size-4 text-destructive" />
          ) : (
            <CheckCircle2 className="size-4 text-emerald-600" />
          )}
          Recommended: Route {rec.label}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{rec.headline}</p>
        {rec.tradeoff && <p className="mt-1 text-sm text-muted-foreground">{rec.tradeoff}</p>}
      </div>
      {rec.warnings.map((w) => (
        <p key={w} className="flex gap-2 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          {w}
        </p>
      ))}
      {plan.notes.map((n) => (
        <p key={n} className="flex gap-2 px-1 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" />
          {n}
        </p>
      ))}
    </section>
  );
});

interface CardsProps {
  plan: Plan;
  selected?: string;
  onSelect: (label: string) => void;
}

export const RouteCards = memo(function RouteCards({ plan, selected, onSelect }: CardsProps) {
  return (
    <section className="grid gap-2" aria-label="Route options">
      {plan.routes.map((r) => (
        <RouteCard
          key={r.label}
          route={r}
          plan={plan}
          recommended={r.label === plan.recommendation.label}
          whyNot={plan.recommendation.why_not[r.label]}
          selected={r.label === selected}
          onSelect={() => onSelect(r.label)}
        />
      ))}
    </section>
  );
});

function RouteCard({
  route: r,
  plan,
  recommended,
  whyNot,
  selected,
  onSelect,
}: {
  route: RouteOption;
  plan: Plan;
  recommended: boolean;
  whyNot?: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const pause = r.total_s - r.drive_s;
  const arrival = Date.parse(r.arrival_at) / 1000;
  const riskyMiles = LEVELS.slice(2)
    .map((l) => ({ ...l, mi: r.miles_by_level[l.key] }))
    .filter((l) => l.mi > 0);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "grid gap-2 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50",
        selected && "border-foreground/60 ring-1 ring-foreground/20",
      )}
    >
      <div className="flex items-center gap-2">
        <span className="grid size-6 place-items-center rounded-md bg-foreground text-xs font-bold text-background">
          {r.label}
        </span>
        <span className="text-sm font-medium">
          {formatMiles(r.distance_mi)} · {formatDuration(r.total_s)}
        </span>
        {recommended && <Badge className="ml-auto bg-emerald-600 text-white">Recommended</Badge>}
        {!recommended && r.source === "via" && (
          <Badge variant="outline" className="ml-auto">
            Forced alternative
          </Badge>
        )}
      </div>
      <RiskStrip checkpoints={r.checkpoints} />
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Clock className="size-3" />
          Arrive {formatLocal(arrival, plan.destination.tz)}
        </span>
        <span>Drive {formatDuration(r.drive_s)}</span>
        {pause > 0 && <span>+{formatDuration(pause)} HOS</span>}
        <span>Avg risk {r.avg_risk === null ? "—" : r.avg_risk.toFixed(2)}</span>
      </div>
      <div className="flex flex-wrap gap-1.5 text-xs">
        {riskyMiles.length === 0 && r.miles_by_level.no_data === 0 && (
          <span className="text-emerald-700">No High, Severe or No-Travel miles</span>
        )}
        {riskyMiles.map((l) => (
          <span key={l.key} className="inline-flex items-center gap-1">
            <span className="size-2 rounded-full" style={{ background: rgbCss(l.rgb) }} />
            {formatMiles(l.mi, 1)} {l.label}
          </span>
        ))}
        {r.miles_by_level.no_data > 0 && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <span className="size-2 rounded-full" style={{ background: rgbCss(NO_DATA.rgb) }} />
            {formatMiles(r.miles_by_level.no_data, 1)} no data
          </span>
        )}
      </div>
      {whyNot && (
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Not recommended:</span> {whyNot}
        </p>
      )}
    </button>
  );
}
