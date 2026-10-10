import type { Checkpoint } from "@/api/types";
import { levelInfo, rgbCss } from "@/lib/risk";

/** Risk along the route, left (origin) to right (destination), by road distance. */
export function RiskStrip({ checkpoints }: { checkpoints: Checkpoint[] }) {
  const total = checkpoints.reduce((s, c) => s + c.share_mi, 0) || 1;
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
      {checkpoints.map((c) =>
        c.share_mi > 0 ? (
          <div
            key={c.i}
            style={{ width: `${(c.share_mi / total) * 100}%`, background: rgbCss(levelInfo(c.level).rgb) }}
          />
        ) : null,
      )}
    </div>
  );
}
