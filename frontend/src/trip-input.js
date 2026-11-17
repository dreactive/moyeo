export function readAnchor(data,key) {
  const label = data[key + '_label'];
  if (!label && !data[key + '_latitude'] && !data[key + '_longitude']) return null;
  if (!label || data[key + '_latitude'] === '' || data[key + '_latitude'] == null || data[key + '_longitude'] === '' || data[key + '_longitude'] == null) throw new Error('거점 명칭·위도·경도를 모두 입력하세요.');
  return {label,latitude:Number(data[key + '_latitude']),longitude:Number(data[key + '_longitude'])};
}
export function readTripConfig(data,fixed_costs) {
  const config = {region:data.region,start_date:data.start_date,end_date:data.end_date,transport:'car',day_start_time:data.day_start_time,day_end_time:data.day_end_time,per_person_budget_krw:Number(data.per_person_budget_krw),fixed_costs};
  ['origin','destination','lodging'].forEach(key => config[key] = readAnchor(data,key));
  return config;
}
export function changedTripFields(edited,baseline) {
  return Object.fromEntries(Object.entries(edited).filter(([key,value]) => JSON.stringify(value) !== JSON.stringify(baseline[key])));
}
export function tripPatch(edited,baseline,latest) {
  const patch = changedTripFields(edited,baseline);
  for (const key of ['origin','destination','lodging']) {
    if (patch[key] && baseline[key] && latest[key]) patch[key] = {...latest[key],...changedTripFields(patch[key],baseline[key])};
  }
  return patch;
}
