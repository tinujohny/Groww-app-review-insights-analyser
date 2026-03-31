/** ISO week helpers for the 8-week analytics strip (aligned with Groww Weekly Pulse UI). */

export function parseIsoWeek(s: string): { y: number; w: number } | null {
  const m = s.trim().match(/^(\d{4})-W(\d{1,2})$/i);
  if (!m) return null;
  return { y: +m[1], w: +m[2] };
}

/** Monday 00:00 UTC of the given ISO week. */
export function mondayOfIsoWeek(year: number, week: number): Date {
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const jan4Dow = jan4.getUTCDay() || 7;
  const mondayWeek1 = new Date(jan4);
  mondayWeek1.setUTCDate(jan4.getUTCDate() - jan4Dow + 1);
  const monday = new Date(mondayWeek1);
  monday.setUTCDate(mondayWeek1.getUTCDate() + (week - 1) * 7);
  return monday;
}

export function dateToIsoWeek(d: Date): { y: number; w: number } {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  t.setUTCDate(t.getUTCDate() + 3 - ((t.getUTCDay() + 6) % 7));
  const week1 = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
  const w =
    1 +
    Math.round(
      ((t.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getUTCDay() + 6) % 7)) / 7,
    );
  return { y: t.getUTCFullYear(), w };
}

export function formatIsoWeek(y: number, w: number): string {
  return `${y}-W${String(w).padStart(2, "0")}`;
}

export function addDaysUtc(d: Date, n: number): Date {
  const x = new Date(d.getTime());
  x.setUTCDate(x.getUTCDate() + n);
  return x;
}

/** Eight ISO week labels ending at the week for `weekBucket` (W1 = oldest … W8 = selected week). */
export function eightWeeksEndingAt(weekBucket: string): string[] {
  const p = parseIsoWeek(weekBucket);
  if (!p) return [];
  const endMonday = mondayOfIsoWeek(p.y, p.w);
  const out: string[] = [];
  for (let i = 0; i < 8; i++) {
    const d = addDaysUtc(endMonday, -7 * (7 - i));
    const { y, w } = dateToIsoWeek(d);
    out.push(formatIsoWeek(y, w));
  }
  return out;
}
