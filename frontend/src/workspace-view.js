const rendered = new Map();
export function renderChanged(key,value,render) {
  const stamp = JSON.stringify(value);
  if (rendered.get(key) === stamp) return;
  if (render() !== false) rendered.set(key,stamp);
}
export function roomMeta(config) {
  const nights = Math.round((Date.parse(config.end_date) - Date.parse(config.start_date)) / 86400000);
  return `${config.start_date} — ${config.end_date} · ${nights}박 ${nights + 1}일 · ${config.region}`;
}
