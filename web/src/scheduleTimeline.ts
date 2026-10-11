// Display positions only; the roster remains the source of shift times.
export function shiftWindow(label: string): { start: number; end: number; continues: boolean } | null {
  const matches = [...label.matchAll(/\b(\d{2}):(\d{2})\b/g)];
  if (!matches.length || matches.some(m => Number(m[1]) > 24 || Number(m[2]) > 59 || (Number(m[1]) === 24 && Number(m[2]) !== 0))) return null;
  const times = matches.map(m => Number(m[1]) * 60 + Number(m[2]));
  const [start, end] = times;
  if (end === undefined) return /\bfrom\b/i.test(label) ? { start, end: 1440, continues: true } : null;
  return { start, end: end <= start ? 1440 : end, continues: end <= start };
}
export function clockPosition(label: string): number | null {
  const match = /^(\d{2}):(\d{2})$/.exec(label);
  if (!match || Number(match[1]) > 23 || Number(match[2]) > 59) return null;
  return (Number(match[1]) * 60 + Number(match[2])) / 1440 * 100;
}
