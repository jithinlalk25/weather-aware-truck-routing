import { memo } from "react";

import type { Plan } from "@/api/types";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROWS = [
  { key: "no_travel", label: "No-Travel miles" },
  { key: "severe", label: "Severe miles" },
  { key: "high", label: "High miles" },
  { key: "avg_risk", label: "Average risk (0–4)" },
  { key: "time", label: "Travel time" },
] as const;

/** The recommendation criteria in priority order; the deciding row is highlighted. */
export const ComparisonTable = memo(function ComparisonTable({ plan }: { plan: Plan }) {
  const routes = [...plan.routes].sort((a, b) => a.rank - b.rank);
  const decided = plan.recommendation.decided_by;
  const value = (r: (typeof routes)[number], key: (typeof ROWS)[number]["key"]) => {
    if (key === "avg_risk") return r.avg_risk === null ? "—" : r.avg_risk.toFixed(2);
    if (key === "time") return formatDuration(r.total_s);
    return r.miles_by_level[key].toFixed(1);
  };
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-medium text-muted-foreground">
        How the recommendation was made (criteria in priority order)
      </h3>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-xs">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Criterion</th>
              {routes.map((r) => (
                <th key={r.label} className="px-2 py-1.5 text-right font-medium">
                  Route {r.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => (
              <tr
                key={row.key}
                className={cn("border-t", decided === row.key && "bg-emerald-50 font-medium")}
              >
                <td className="px-2 py-1.5">
                  {i + 1}. {row.label}
                </td>
                {routes.map((r) => (
                  <td
                    key={r.label}
                    className={cn(
                      "px-2 py-1.5 text-right tabular-nums",
                      r.label === plan.recommendation.label && "font-semibold",
                    )}
                  >
                    {value(r, row.key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
});
