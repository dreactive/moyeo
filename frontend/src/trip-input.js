export function readAnchor(data,key) {
  const label = data[key + '_label'];
  if (!label && !data[key + '_latitude'] && !data[key + '_longitude']) return null;
  if (!label || data[key + '_latitude'] === '' || data[key + '_latitude'] == null || data[key + '_longitude'] === '' || data[key + '_longitude'] == null) throw new Error('장소 검색이나 지도에서 위치를 골라 주세요.');
  const anchor = {label,latitude:Number(data[key + '_latitude']),longitude:Number(data[key + '_longitude'])};
  if (data[key + '_source_ref']) anchor.source_ref = data[key + '_source_ref'];
  return anchor;
}
export const ANCHOR_KEYS = ['lodging'];
const blank = value => value == null || String(value).trim() === '';
export function requireTripBasics(config) {
  if (!config.region) throw new Error('도시를 입력하세요.');
  if (config.per_person_budget_krw == null) throw new Error('1인 전체 예산을 입력하세요.');
  return config;
}
export function readTripConfig(data,fixed_costs) {
  const budget = blank(data.per_person_budget_krw) ? null : Number(data.per_person_budget_krw);
  if (budget !== null && !(Number.isInteger(budget) && budget >= 0)) throw new Error('예산은 0 이상의 정수로 입력하세요.');
  const config = {
    region:String(data.region ?? '').trim(),
    start_date:blank(data.start_date) ? null : data.start_date,
    end_date:blank(data.end_date) ? null : data.end_date,
    transport:'car',
    day_start_time:blank(data.day_start_time) ? '09:00' : data.day_start_time,
    day_end_time:blank(data.day_end_time) ? '18:00' : data.day_end_time,
    per_person_budget_krw:budget,
    fixed_costs,
  };
  if (config.start_date && config.end_date && config.end_date < config.start_date) throw new Error('종료일은 시작일보다 빠를 수 없어요.');
  ANCHOR_KEYS.forEach(key => config[key] = readAnchor(data,key));
  return config;
}
export function changedTripFields(edited,baseline) {
  return Object.fromEntries(Object.entries(edited).filter(([key,value]) => JSON.stringify(value) !== JSON.stringify(baseline[key])));
}
export function tripPatch(edited,baseline,latest) {
  const patch = changedTripFields(edited,baseline);
  for (const key of ANCHOR_KEYS) {
    if (patch[key] && baseline[key] && latest[key]) {
      const changed = changedTripFields(patch[key],baseline[key]);
      patch[key] = {...latest[key],...changed};
      if (!edited[key].source_ref && ('latitude' in changed || 'longitude' in changed)) delete patch[key].source_ref;
    }
  }
  if (patch.fixed_costs) patch.fixed_costs = mergeCostEdits(edited.fixed_costs,baseline.fixed_costs,latest.fixed_costs);
  return patch;
}
function mergeCostEdits(edited,baseline,latest) {
  const find = (lines,id) => lines.find(line => line.id === id);
  return latest.filter(line => !find(baseline,line.id) || find(edited,line.id)).map(line => {
    const before = find(baseline,line.id);
    const after = find(edited,line.id);
    return before && after ? {...line,...changedTripFields(after,before)} : line;
  }).concat(edited.filter(line => !find(baseline,line.id)));
}
