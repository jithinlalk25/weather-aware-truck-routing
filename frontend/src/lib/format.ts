/** "25h 36m" or "30m" (same style as the backend's explanations). */
export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

export const formatMiles = (mi: number, digits = 0) =>
  `${mi.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })} mi`;

const fmtCache = new Map<string, Intl.DateTimeFormat>();

function dtf(tz: string, withDay: boolean) {
  const key = `${tz}|${withDay}`;
  let f = fmtCache.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      weekday: withDay ? "short" : undefined,
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
    fmtCache.set(key, f);
  }
  return f;
}

/** "Sat 8:05 PM CDT" in the given IANA zone. */
export function formatLocal(epochS: number, tz: string, withDay = true): string {
  return dtf(tz, withDay).format(new Date(epochS * 1000));
}

export function formatElapsed(seconds: number): string {
  return `T+${formatDuration(seconds)}`;
}

/** Wall-clock "YYYY-MM-DDTHH:mm" for an instant in a zone (for datetime-local inputs). */
export function toLocalInput(date: Date, tz: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(date)
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function tzAbbrev(tz: string, at = new Date()): string {
  const part = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "short" })
    .formatToParts(at)
    .find((p) => p.type === "timeZoneName");
  return part?.value ?? tz;
}
