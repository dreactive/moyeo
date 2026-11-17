import {escapeHtml as e,money} from './ui.js';
let routeElement, placeElement;
export function initMaps(options) { ({routeElement,placeElement} = options); prepareSdk(options.appKey); }
export function renderRouteMap(plan, placesById, config) {
  lastRoute = [plan,placesById,config];
  if (sdk) return drawKakao(sdk,routeElement,[config.origin,config.lodging,config.destination,...(plan?.days.flatMap(day => day.visits.map(visit => placesById.get(visit.place_ref))) ?? [])].filter(Boolean),plan?.days.flatMap(day => day.route_legs.map(leg => leg.polyline)) ?? []);
  routeElement.innerHTML = `<strong>지도 키 미설정 · 좌표/서버 경로 대역 (실지도 아님)</strong>
  <p>revision ${e(plan?.plan_revision ?? '없음')}</p>
  ${['origin','lodging','destination'].map(key => `<p>${key}: ${e(JSON.stringify(config[key]))}</p>`).join('')}
  ${plan?.days.map(day => `<h3>${e(day.date)}</h3><ol>${day.visits.map(visit => `<li>${e(placesById.get(visit.place_ref)?.name ?? visit.place_ref)} · ${e(JSON.stringify(placesById.get(visit.place_ref)?.latitude))}, ${e(JSON.stringify(placesById.get(visit.place_ref)?.longitude))}</li>`).join('')}</ol>
  ${day.route_legs.map(leg => `<p>${e(leg.from_ref)} → ${e(leg.to_ref)} · ${leg.distance_m}m · ${leg.duration_seconds}초 · 통행료 ${money(leg.toll_krw)} · 근거 ${e(leg.evidence_id)}</p><pre>서버 polyline ${e(JSON.stringify(leg.polyline))}</pre>`).join('')}`).join('') ?? ''}`;
}
export function renderPlaceMap(place) {
  lastPlace = place;
  if (sdk && place) return drawKakao(sdk,placeElement,[place]);
  placeElement.innerHTML = place ? `개인 지도 대역 · ${e(place.name)}<p>${e(place.latitude)}, ${e(place.longitude)}</p>` : '개인 지도 · 장소를 선택하세요.';
}
import {loadKakao,drawKakao} from './kakao-adapter.js';
let sdk = null;
let lastRoute = null;
let lastPlace = null;
async function prepareSdk(appKey) {
  try {
    sdk = await loadKakao(appKey);
    if (sdk && lastRoute) renderRouteMap(...lastRoute);
    if (sdk && lastPlace) renderPlaceMap(lastPlace);
  } catch(error) { routeElement.insertAdjacentHTML('afterbegin','<p>' + e(error.message) + '</p>'); }
}
