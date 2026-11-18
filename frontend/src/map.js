import {escapeHtml as e,money} from './ui.js';
const anchorLabels = {origin:'출발지',lodging:'숙소',destination:'귀가지'};
let routeElement, placeElement;
export function initMaps(options) {
  ({routeElement,placeElement} = options);
  sdkMessage = options.appKey ? '지도를 불러오는 중' : '지도 키 미설정';
  return prepareSdk(options.appKey);
}
export function renderRouteMap(plan, placesById, config, date) {
  lastRoute = [plan,placesById,config,date];
  if (!plan) return fallback(routeElement,'<p class="map-placeholder">여행안이 준비되면 동선을 볼 수 있어요.</p>');
  const days = plan.days;
  const selected = days.find(day => day.date === date) ?? days[0];
  const visibleDays = date != null && selected ? [selected] : days;
  const anchorKeys = date != null && selected ? dailyAnchors(days,selected) : ['origin','lodging','destination'];
  if (sdk) return drawKakao(sdk,routeElement,[...anchorKeys.map(key => config[key]),...visibleDays.flatMap(day => day.visits.map(visit => placesById.get(visit.place_ref)))].filter(Boolean),visibleDays.flatMap(day => day.route_legs.map(leg => leg.polyline)));
  fallback(routeElement,`<strong>${sdkMessage} · 좌표와 서버 경로</strong>

  <ul>${anchorKeys.map(key => `<li>${e(config[key]?.label ?? anchorLabels[key])} · ${coordinates(config[key])}</li>`).join('')}</ul>
  ${visibleDays.map(day => `<h3>${e(day.date)}</h3><ol>${day.visits.map(visit => `<li>${e(placesById.get(visit.place_ref)?.name ?? visit.place_ref)} · ${coordinates(placesById.get(visit.place_ref))}</li>`).join('')}</ol>
  ${day.route_legs.map(routeLegMarkup).join('')}`).join('')}`);
}
function routeLegMarkup(leg) {
  return `<p>${e(leg.from_ref)} → ${e(leg.to_ref)} · ${e(leg.distance_m)}m · ${e(leg.duration_seconds)}초 · 통행료 ${money(leg.toll_krw)}</p>
    <details><summary>서버 polyline</summary><p>근거 ${e(leg.evidence_id)}</p><pre>${e(JSON.stringify(leg.polyline))}</pre></details>`;
}
function coordinates(point) {
  if (point?.latitude == null || point.longitude == null) return '좌표 미확인';
  return `${e(point.latitude)}, ${e(point.longitude)}`;
}
function dailyAnchors(days,day) {
  const start = day === days[0] ? 'origin' : 'lodging';
  const end = day === days.at(-1) ? 'destination' : 'lodging';
  return [...new Set([start,end])];
}
export function renderPlaceMap(place) {
  lastPlace = place;
  if (sdk && place) return drawKakao(sdk,placeElement,[place]);
  fallback(placeElement,place ? `<strong>${sdkMessage} · ${e(place.name)}</strong><p>${coordinates(place)}</p>` : '<p class="map-placeholder">장소를 선택하세요.</p>');
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
