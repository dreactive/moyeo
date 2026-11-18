import {escapeHtml as e,money} from './ui.js';
import {agreementMarkup,itemAgreement,planItemAgreements} from './agreement.js';
import {hasCurrentBasis} from './plan.js';
const anchorLabels = {origin:'출발지',lodging:'숙소',destination:'귀가지'};
let routeElement, placeElement;
export function initMaps(options) {
  ({routeElement,placeElement} = options);
  sdkMessage = options.appKey ? '지도를 불러오는 중' : '지도 키 미설정';
  return prepareSdk(options.appKey);
}
export function locatedMentions(snapshot,plan) {
  if (!snapshot || (plan && !hasCurrentBasis(snapshot,plan.confirmation_target))) return [];
  const scheduled = new Set(plan?.days?.flatMap(day => day.visits.map(v => v.item_id)) ?? []);
  const versions = new Map(plan?.item_snapshots?.map(i => [i.id,i.item_version]) ?? []);
  const unplaced = new Map(plan?.unplaced_items?.map(i => [i.item_id,i.place_ref]) ?? []);
  return (snapshot.items ?? []).flatMap(item => {
    if (item.kind !== 'place' || scheduled.has(item.id)) return [];
    const planRef = versions.get(item.id) === item.item_version && unplaced.get(item.id);
    const observedRef = item.place_source_refs?.length && (!item.place_region || item.place_region === snapshot.config.region)
      ? item.place_ref : null;
    const ref = planRef || observedRef;
    return ref ? [{id:item.id,ref,title:item.title,unplaced:!!planRef,agreement:itemAgreement(snapshot,item,plan)}] : [];
  });
}

export function renderRouteMap(plan,placesById,config,date,snapshot) {
  lastRoute = [plan,placesById,config,date,snapshot];
  const mentions = locatedMentions(snapshot,plan);
  if (!plan && !mentions.length) return fallback(routeElement,'<p class="map-placeholder">여행안이 준비되면 동선을 볼 수 있어요.</p>');
  const days = plan?.days ?? [];
  const selected = days.find(day => day.date === date) ?? days[0];
  const visibleDays = date != null && selected ? [selected] : days;
  const anchorKeys = !plan ? [] : date != null && selected ? dailyAnchors(days,selected) : ['origin','lodging','destination'];
  const agreements = snapshot && planItemAgreements(snapshot,plan);
  if (sdk) {
    const visits = visibleDays.flatMap(day => day.visits.map((visit,index) => {
      const place = placesById.get(visit.place_ref);
      const agreement = agreements?.get(visit.item_id) ?? (agreements && {state:'pending',label:'동의 미확인'});
      return place && {...place,visitNumber:index + 1,agreement};
    }));
    const mentionedPoints = mentions.map(m => ({...placesById.get(m.ref),name:m.title,
      mention:true,unplaced:m.unplaced,agreement:m.agreement}));
    const points = [...anchorKeys.map(key => config[key]),...visits,...mentionedPoints].filter(hasCoordinates);
    const lines = visibleDays.flatMap(day => day.route_legs.map(leg => leg.polyline)).filter(hasGeometry);
    const map = tryDraw(routeElement,points,lines);
    if (map) return map;
  }
  const names = new Map(plan?.item_snapshots.map(item => [item.place_ref,item.title]) ?? []);
  for (const key of anchorKeys) names.set('anchor:' + key, config[key]?.label ?? anchorLabels[key]);
  const label = ref => e(names.get(ref) ?? placesById.get(ref)?.name ?? ref);
  fallback(routeElement,`<strong>${fallbackMessage()} · 좌표와 서버 경로</strong>
  <ul>${anchorKeys.map(key => `<li>${label('anchor:' + key)} · ${coordinates(config[key])}</li>`).join('')}</ul>
  ${mentions.length ? `<ul>${mentions.map(m => `<li>${e(m.title)} · ${coordinates(placesById.get(m.ref))}
    · ${m.unplaced ? '일정 미배치' : '방문 일정 미정'} ${agreementMarkup(m.agreement)}</li>`).join('')}</ul>` : ''}
  ${visibleDays.map(day => `<h3>${e(day.date)}</h3><ol>${day.visits.map(visit => `<li>${label(visit.place_ref)} · ${coordinates(placesById.get(visit.place_ref))}
    ${agreements ? agreementMarkup(agreements.get(visit.item_id)) : ''}</li>`).join('')}</ol>
  ${day.route_legs.map(leg => routeLegMarkup(leg,label)).join('')}`).join('')}`);
}
export function routeLegMarkup(leg,label) {
  return `<p>${label(leg.from_ref)} → ${label(leg.to_ref)} · ${leg.distance_m == null ? '거리 미확인' : `${e(leg.distance_m)}m`}
    · ${leg.duration_seconds == null ? '소요 시간 미확인' : `${e(leg.duration_seconds)}초`} · 통행료 ${money(leg.toll_krw)}
    ${leg.departure_at ? ` · 출발 기준 ${e(leg.departure_at)}` : ''}</p>
    ${hasGeometry(leg.polyline) ? `<details><summary>서버 polyline</summary><p>근거 ${e(leg.evidence_id)}</p><pre>${e(JSON.stringify(leg.polyline))}</pre></details>`
      : `<p class="muted">경로선 미확인${leg.evidence_id ? ` · 근거 ${e(leg.evidence_id)}` : ''}</p>`}`;
}
export const hasCoordinates = point => Number.isFinite(point?.latitude) && Number.isFinite(point?.longitude);
const hasGeometry = polyline => Array.isArray(polyline) && polyline.length > 1 && polyline.every(hasCoordinates);
function coordinates(point) {
  if (!hasCoordinates(point)) return '좌표 미확인';
  return `${e(point.latitude)}, ${e(point.longitude)}`;
}
export function dailyAnchors(days,day) {
  const start = day === days[0] ? 'origin' : 'lodging';
  const end = day === days.at(-1) ? 'destination' : 'lodging';
  return [...new Set([start,end])];
}
export function renderPlaceMap(place) {
  lastPlace = place;
  const map = sdk && hasCoordinates(place) && tryDraw(placeElement,[place]);
  if (map) return map;
  fallback(placeElement,place ? `<strong>${fallbackMessage()} · ${e(place.name)}</strong><p>${coordinates(place)}</p>` : '<p class="map-placeholder">장소를 선택하세요.</p>');
}
function tryDraw(element, points, lines) {
  try {
    return drawKakao(sdk,element,points,lines);
  } catch {
    return null;
  }
}
function fallbackMessage() {
  return sdk ? '지도를 표시할 수 없어요' : sdkMessage;
}
function fallback(element, markup) {
  clearKakao(element);
  element.innerHTML = markup;
}
import {loadKakao,drawKakao,clearKakao} from './kakao-adapter.js';
let sdk = null;
let sdkMessage;
let lastRoute = null;
let lastPlace = null;
async function prepareSdk(appKey) {
  try {
    sdk = await loadKakao(appKey);
  } catch {
    sdkMessage = '지도를 불러오지 못했어요';
  }
  if (!appKey) return;
  if (lastRoute) renderRouteMap(...lastRoute);
  if (lastPlace) renderPlaceMap(lastPlace);
}
