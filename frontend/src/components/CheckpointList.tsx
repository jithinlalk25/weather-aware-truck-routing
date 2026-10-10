import { ChevronDown } from "lucide-react";
import { useState } from "react";

import type { RouteOption } from "@/api/types";
import { formatLocal } from "@/lib/format";
import { levelInfo, rgbCss } from "@/lib/risk";

export function CheckpointList({ route }: { route: RouteOption }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-lg border">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        Route {route.label} checkpoints ({route.checkpoints.length})
        <ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="max-h-80 overflow-y-auto border-t">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-background text-muted-foreground">
              <tr>
                <th className="px-2 py-1 text-left font-medium">Mile</th>
                <th className="px-2 py-1 text-left font-medium">ETA</th>
                <th className="px-2 py-1 text-left font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {route.checkpoints.map((c) => {
                const info = levelInfo(c.level);
                return (
                  <tr key={c.i} className="border-t align-top">
                    <td className="px-2 py-1 tabular-nums">{c.dist_mi.toFixed(0)}</td>
                    <td className="px-2 py-1 whitespace-nowrap">{formatLocal(c.eta, c.tz)}</td>
                    <td className="px-2 py-1">
                      <span className="inline-flex items-center gap-1 font-medium">
                        <span className="size-2 rounded-full" style={{ background: rgbCss(info.rgb) }} />
                        {info.label}
                      </span>
                      {c.factor && <div className="text-muted-foreground">{c.factor}</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
