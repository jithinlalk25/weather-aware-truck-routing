import { CloudSun, Loader2, RefreshCw } from "lucide-react";
import { lazy, type ReactNode, Suspense, useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError } from "@/api/client";
import { useCreatePlan, useHeatmap, usePlan } from "@/api/hooks";
import type { HeatmapLayerKey, Plan, PlanRequest } from "@/api/types";
import { CheckpointList } from "@/components/CheckpointList";
import { ComparisonTable } from "@/components/ComparisonTable";
import { type DockLayer, ForecastDock } from "@/components/ForecastDock";
import { RecommendationCard, RouteCards } from "@/components/RouteCards";
import { TripForm } from "@/components/TripForm";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useHeatmapFrame } from "@/hooks/useHeatmapFrame";
import { toLocalInput } from "@/lib/format";
import { defaultValues, valuesFromPlan } from "@/lib/formValues";
import { RAMPS } from "@/lib/risk";
import { truckAt } from "@/lib/timeline";

const MapView = lazy(() => import("@/map/MapView").then((m) => ({ default: m.MapView })));

function requestFromPlan(plan: Plan): PlanRequest {
  const departure = Math.max(Date.parse(plan.departure_at), Date.now() + 60_000);
  return {
    origin: plan.origin,
    destination: plan.destination,
    departure_local: toLocalInput(new Date(departure), plan.origin.tz),
    load_lb: plan.load_lb,
    interval_mi: plan.interval_mi,
    wind_mode: plan.wind_mode,
    hos: plan.hos_enabled,
  };
}

export function TripPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const planQuery = usePlan(id);
  const create = useCreatePlan();
  const plan = planQuery.data;

  const submit = useCallback(
    (req: PlanRequest) => create.mutate(req, { onSuccess: (p) => navigate(`/trip/${p.id}`) }),
    [create, navigate],
  );
  const notFound = planQuery.error instanceof ApiError && planQuery.error.status === 404;

  const form = useMemo(
    () => (plan ? valuesFromPlan(plan) : defaultValues()),
    [plan],
  );

  const sidebarTop =
    id && planQuery.isPending ? (
      <div className="grid gap-3">
        <Skeleton className="h-9" />
        <Skeleton className="h-9" />
        <Skeleton className="h-24" />
      </div>
    ) : notFound ? (
      <div className="grid gap-2 text-sm">
        <p>This trip plan doesn't exist.</p>
        <Button asChild variant="outline">
          <Link to="/">Plan a new trip</Link>
        </Button>
      </div>
    ) : (
      <TripForm
        key={plan?.id ?? "new"}
        initial={form}
        pending={create.isPending}
        error={create.error}
        autoApplyOptions={!!plan}
        onSubmit={submit}
      />
    );

  return (
    <TripView
      plan={plan}
      sidebarTop={sidebarTop}
      planning={create.isPending}
      onRefresh={plan ? () => submit(requestFromPlan(plan)) : undefined}
    />
  );
}

interface ViewProps {
  plan: Plan | undefined;
  sidebarTop: ReactNode;
  planning: boolean;
  onRefresh?: () => void;
}

function TripView({ plan, sidebarTop, planning, onRefresh }: ViewProps) {
  const [selected, setSelected] = useState(plan?.recommendation.label);
  const [hour, setHour] = useState(0);
  // Reset per-plan state when a new plan arrives, without remounting the map.
  const [shownPlanId, setShownPlanId] = useState(plan?.id);
  if (plan?.id !== shownPlanId) {
    setShownPlanId(plan?.id);
    setSelected(plan?.recommendation.label);
    setHour(0);
  }
  const [layer, setLayer] = useState<DockLayer>("risk");
  const [showHeat, setShowHeat] = useState(true);

  const heatQuery = useHeatmap(plan?.id);
  const dataKey: HeatmapLayerKey = layer === "wind" && plan?.wind_mode === "gust" ? "gust" : layer;
  const frame = useHeatmapFrame(heatQuery.data, dataKey, RAMPS[layer], hour, showHeat);

  const route = plan?.routes.find((r) => r.label === selected);
  const truck = useMemo(
    () => (route ? truckAt(route.path, route.rest_stops, hour * 3600) : null),
    [route, hour],
  );

  return (
    <div className="flex min-h-dvh flex-col md:h-dvh md:flex-row">
      <aside className="order-2 flex flex-col border-t bg-background md:order-1 md:w-[26rem] md:shrink-0 md:overflow-y-auto md:border-t-0 md:border-r">
        <header className="flex items-center gap-2 border-b px-4 py-3">
          <CloudSun className="size-5 text-sky-600" />
          <div className="grid">
            <Link to="/" className="text-sm leading-tight font-semibold">
              Weather-Aware Truck Routing
            </Link>
            <span className="text-xs text-muted-foreground">
              Three truck routes, scored on forecast weather along the way
            </span>
          </div>
        </header>

        <div className="grid gap-5 p-4">
          {sidebarTop}
          {plan && (
            <>
              <RecommendationCard plan={plan} />
              <RouteCards plan={plan} selected={selected} onSelect={setSelected} />
              <ComparisonTable plan={plan} />
              {route && <CheckpointList key={route.label} route={route} />}
              <footer className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  Forecast fetched {new Date(plan.created_at).toLocaleString()} ·{" "}
                  {plan.weather_meta.locations} forecast cells
                </span>
                <Button variant="ghost" size="xs" disabled={planning} onClick={onRefresh}>
                  <RefreshCw /> Refresh
                </Button>
              </footer>
            </>
          )}
        </div>
      </aside>

      <main className="relative order-1 h-[58dvh] md:order-2 md:h-auto md:flex-1">
        <Suspense fallback={<div className="absolute inset-0 bg-muted" />}>
          <MapView plan={plan} selected={selected} onSelect={setSelected} heatmap={frame} truck={truck} />
        </Suspense>
        {planning && (
          <div className="pointer-events-none absolute inset-x-0 top-4 flex justify-center">
            <div className="flex items-center gap-2 rounded-full border bg-background/95 px-4 py-2 text-sm shadow">
              <Loader2 className="size-4 animate-spin" /> Routing and sampling forecasts…
            </div>
          </div>
        )}
        {plan && (
          <div className="pointer-events-none absolute inset-x-2 bottom-2 md:inset-x-auto md:right-4 md:bottom-6 md:left-4 lg:left-auto lg:w-[40rem]">
            <ForecastDock
              plan={plan}
              routeLabel={selected}
              hour={hour}
              onHour={setHour}
              layer={layer}
              onLayer={setLayer}
              show={showHeat}
              onShow={setShowHeat}
              truck={truck}
              heatmapStatus={heatQuery.status}
              heatmapError={heatQuery.error?.message}
              onRetry={() => heatQuery.refetch()}
            />
          </div>
        )}
      </main>
    </div>
  );
}
