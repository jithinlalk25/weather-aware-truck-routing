import "maplibre-gl/dist/maplibre-gl.css";

import { COORDINATE_SYSTEM, type Layer, type PickingInfo } from "@deck.gl/core";
import { BitmapLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapLibreOverlay, type MapLibreOverlayProps } from "@deck.gl/maplibre";
import { setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map as MapGL, type MapRef, NavigationControl, useControl } from "react-map-gl/maplibre";

import type { Checkpoint, Plan, RestStop, RouteOption } from "@/api/types";
import { formatDuration, formatElapsed, formatLocal, formatMiles } from "@/lib/format";
import type { HeatmapFrame } from "@/lib/heatmapImage";
import { levelInfo, type RGB } from "@/lib/risk";
import { riskRuns, type RiskRun, type TruckState } from "@/lib/timeline";

setWorkerUrl(workerUrl);

const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const INITIAL_VIEW = { longitude: -96.5, latitude: 38.5, zoom: 3.6 };
const ATTRIBUTION =
  'Weather <a href="https://open-meteo.com/" target="_blank">Open-Meteo</a> (CC BY 4.0) · Routing © <a href="https://www.tomtom.com/" target="_blank">TomTom</a>';

function DeckOverlay(props: MapLibreOverlayProps) {
  const overlay = useControl<MapLibreOverlay>(() => new MapLibreOverlay(props));
  overlay.setProps(props);
  return null;
}

interface Props {
  plan?: Plan;
  selected?: string;
  onSelect: (label: string) => void;
  heatmap: HeatmapFrame | null;
  truck: TruckState | null;
}

type Picked =
  | { kind: "checkpoint"; route: string; cp: Checkpoint }
  | { kind: "stop"; route: string; stop: RestStop }
  | { kind: "route"; route: RouteOption };

const UNSELECTED: RGB = [100, 116, 139];

function MapViewImpl({ plan, selected, onSelect, heatmap, truck }: Props) {
  const mapRef = useRef<MapRef>(null);
  const [labelLayerId, setLabelLayerId] = useState<string>();
  const [loaded, setLoaded] = useState(false);

  const onLoad = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    setLabelLayerId(map.getStyle().layers.find((l) => l.type === "symbol")?.id);
    // Start the compact attribution collapsed so it doesn't cover the forecast dock.
    map.getContainer().querySelector(".maplibregl-compact-show")?.classList.remove("maplibregl-compact-show");
    setLoaded(true);
  }, []);

  // Frame all routes whenever a new plan arrives (the map instance is created asynchronously).
  useEffect(() => {
    const map = mapRef.current;
    if (!loaded || !map || !plan) return;
    let [w, s, e, n] = [180, 90, -180, -90];
    for (const r of plan.routes)
      for (const [lon, lat] of r.path) {
        w = Math.min(w, lon);
        e = Math.max(e, lon);
        s = Math.min(s, lat);
        n = Math.max(n, lat);
      }
    map.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: { top: 60, bottom: 160, left: 60, right: 60 }, duration: 800 },
    );
  }, [plan, loaded]);

  const route = plan?.routes.find((r) => r.label === selected);
  const runs = useMemo<RiskRun[]>(
    () => (route ? riskRuns(route.path, route.checkpoints) : []),
    [route],
  );

  const staticLayers = useMemo(() => {
    if (!plan) return [];
    const others = plan.routes.filter((r) => r.label !== selected);
    const layers: Layer[] = [
      new PathLayer<RouteOption>({
        id: "routes-other",
        data: others,
        getPath: (r) => r.path.map((v): [number, number] => [v[0], v[1]]),
        getColor: [...UNSELECTED, 200],
        getWidth: 5,
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        pickable: true,
        autoHighlight: true,
        highlightColor: [30, 41, 59, 230],
        onClick: ({ object }) => object && onSelect(object.label),
      }),
    ];
    if (route) {
      layers.push(
        new PathLayer<RouteOption>({
          id: "route-casing",
          data: [route],
          getPath: (r) => r.path.map((v): [number, number] => [v[0], v[1]]),
          getColor: [15, 23, 42, 230],
          getWidth: 10,
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
        }),
        new PathLayer<RiskRun>({
          id: "route-risk",
          data: runs,
          getPath: (r) => r.path,
          getColor: (r) => levelInfo(r.level).rgb,
          getWidth: 6,
          widthUnits: "pixels",
          capRounded: true,
          jointRounded: true,
        }),
        new ScatterplotLayer<Checkpoint>({
          id: "checkpoints",
          data: route.checkpoints,
          getPosition: (c) => [c.lon, c.lat],
          getFillColor: (c) => levelInfo(c.level).rgb,
          getLineColor: [255, 255, 255],
          getRadius: 5,
          radiusUnits: "pixels",
          lineWidthUnits: "pixels",
          getLineWidth: 1.5,
          stroked: true,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 120],
        }),
        new ScatterplotLayer<RestStop>({
          id: "rest-stops",
          data: route.rest_stops,
          getPosition: (s) => [s.lon, s.lat],
          getFillColor: (s) => (s.kind === "rest" ? [30, 64, 175] : [255, 255, 255]),
          getLineColor: [30, 64, 175],
          getRadius: (s) => (s.kind === "rest" ? 7 : 5),
          radiusUnits: "pixels",
          lineWidthUnits: "pixels",
          getLineWidth: 2.5,
          stroked: true,
          pickable: true,
        }),
      );
    }
    layers.push(
      new ScatterplotLayer<{ pos: [number, number]; origin: boolean }>({
        id: "endpoints",
        data: [
          { pos: [plan.origin.lon, plan.origin.lat], origin: true },
          { pos: [plan.destination.lon, plan.destination.lat], origin: false },
        ],
        getPosition: (d) => d.pos,
        getFillColor: (d) => (d.origin ? [255, 255, 255] : [15, 23, 42]),
        getLineColor: [15, 23, 42],
        getRadius: 8,
        radiusUnits: "pixels",
        lineWidthUnits: "pixels",
        getLineWidth: 3,
        stroked: true,
      }),
    );
    return layers;
  }, [plan, selected, route, runs, onSelect]);

  const layers = useMemo(() => {
    const out: Layer[] = [];
    if (heatmap) {
      out.push(
        new BitmapLayer({
          id: "heatmap",
          image: heatmap.canvas,
          bounds: heatmap.bounds,
          _imageCoordinateSystem: COORDINATE_SYSTEM.LNGLAT,
          beforeId: labelLayerId,
        } as ConstructorParameters<typeof BitmapLayer>[0]),
      );
    }
    out.push(...staticLayers);
    if (truck) {
      out.push(
        new ScatterplotLayer<TruckState>({
          id: "truck",
          data: [truck],
          getPosition: (t) => [t.lon, t.lat],
          getFillColor: (t) => (t.status === "driving" ? [37, 99, 235] : [100, 116, 139]),
          getLineColor: [255, 255, 255],
          getRadius: 10,
          radiusUnits: "pixels",
          lineWidthUnits: "pixels",
          getLineWidth: 3,
          stroked: true,
          updateTriggers: { getFillColor: truck.status },
        }),
      );
    }
    return out;
  }, [heatmap, staticLayers, truck, labelLayerId]);

  const getTooltip = useCallback(
    (info: PickingInfo) => {
      if (!info.object || !plan) return null;
      const picked = toPicked(info, selected);
      return picked ? { html: tooltipHtml(picked, plan), style: TOOLTIP_STYLE } : null;
    },
    [plan, selected],
  );

  return (
    <MapGL
      ref={mapRef}
      initialViewState={INITIAL_VIEW}
      mapStyle={BASEMAP}
      onLoad={onLoad}
      attributionControl={{ compact: true, customAttribution: ATTRIBUTION }}
      style={{ position: "absolute", inset: 0 }}
      dragRotate={false}
    >
      <NavigationControl position="top-right" showCompass={false} />
      <DeckOverlay interleaved layers={layers} getTooltip={getTooltip} />
    </MapGL>
  );
}

export const MapView = memo(MapViewImpl);

function toPicked(info: PickingInfo, selected?: string): Picked | null {
  const id = info.layer?.id;
  if (id === "checkpoints") return { kind: "checkpoint", route: selected!, cp: info.object };
  if (id === "rest-stops") return { kind: "stop", route: selected!, stop: info.object };
  if (id === "routes-other") return { kind: "route", route: info.object };
  return null;
}

const TOOLTIP_STYLE = {
  background: "white",
  color: "#0f172a",
  borderRadius: "8px",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.18)",
  padding: "10px 12px",
  fontSize: "12px",
  lineHeight: "1.45",
  maxWidth: "280px",
  fontFamily: "inherit",
};

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function tooltipHtml(p: Picked, plan: Plan): string {
  const dep = Date.parse(plan.departure_at) / 1000;
  if (p.kind === "route") {
    const r = p.route;
    return `<b>Route ${r.label}</b> · ${formatMiles(r.distance_mi)} · ${formatDuration(r.total_s)}<br/><span style="color:#64748b">Click to select</span>`;
  }
  if (p.kind === "stop") {
    const s = p.stop;
    const what = s.kind === "rest" ? "10-hour off-duty rest" : "30-minute break";
    return `<b>HOS ${what}</b><br/>Mile ${s.dist_mi.toFixed(0)} · starts ${esc(formatLocal(dep + s.start_elapsed_s, s.tz))}`;
  }
  const c = p.cp;
  const info = levelInfo(c.level);
  const swatch = `<span style="display:inline-block;width:9px;height:9px;border-radius:9px;background:rgb(${info.rgb.join(",")});margin-right:5px"></span>`;
  const head = `<b>Route ${p.route} · mile ${c.dist_mi.toFixed(1)}</b><br/>ETA ${esc(formatLocal(c.eta, c.tz))} <span style="color:#64748b">(${formatElapsed(c.elapsed_s)})</span>`;
  const level = `<div style="margin-top:6px">${swatch}<b>${info.label}</b>${c.factor ? ` — ${esc(c.factor)}` : ""}</div>`;
  if (c.level === null) return head + level;
  const wx = `<div style="margin-top:4px;color:#334155">Wind ${c.wind_mph!.toFixed(0)} mph (gust ${c.gust_mph!.toFixed(0)}) · Rain ${c.rain_in_hr!.toFixed(2)} in/hr · Snow ${c.snow_in_hr!.toFixed(2)} in/hr${c.temp_f != null ? ` · ${c.temp_f}°F` : ""}</div>`;
  const conf = `<div style="margin-top:4px;color:#64748b">Forecast confidence: ${c.confidence} · covers ${c.share_mi.toFixed(1)} mi</div>`;
  return head + level + wx + conf;
}
