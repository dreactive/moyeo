import {html,escapeHtml as e,money} from './ui.js';
export const safeUrl = value => /^https?:\/\//i.test(value ?? '') ? value : '';
const fieldLabels = {menu_price:'메뉴 가격',opening_hours:'영업시간'};
const observationLabels = {api_observed:'공급자 조회',missing:'미확인',user_provided:'사용자 입력',estimated:'추정'};
const matchLabels = {matched:'장소 일치',ambiguous:'장소 일치 확인 필요',unmatched:'다른 장소'};
const modeLabels = {live:'실제 조회',fixture:'개발 대역'};
function evidenceLink(value) {
  const url = safeUrl(value);
  return url ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">출처 열기</a>` : '';
}
export function renderPlace(details) {
  if (!details) return html('place','동선에서 장소를 선택해 주세요.');
  const plan = displayPlan(getSnapshot() ?? {});
  const ref = details.place.id;
  const included = plan?.days.some(day => day.visits.some(visit => visit.place_ref === ref));
  html('place', `<h3>${e(details.place.name)}</h3>
  ${included ? `<p class="place-context">표시 여행안에 포함 <button type="button" data-route-place="${e(ref)}">동선에서 보기</button></p>` : ''}
  <dl class="card-facts">
    <dt>주소</dt><dd>${e(details.place.address || '미확인')}</dd>
    <dt>영업시간</dt><dd>${e(details.opening_hours?.raw_text ?? '미확인')}</dd>
    <dt>휴일</dt><dd>${e(details.opening_hours?.holiday_text ?? '미확인')}</dd>
  </dl>
  <h3>메뉴</h3>${details.menus.map(menu => `<p>${e(menu.name)} · ${menu.price_krw == null ? e(menu.price_text || '미확인') + ' (금액 미확인)' : money(menu.price_krw)} · ${e(menu.serving_basis ?? '제공 단위 미확인')}</p>`).join('') || '<p>메뉴 미등록 · 가격 미확인</p>'}
  <details class="card-details"><summary>장소 정보 출처</summary>
  <p>좌표 ${e(details.place.latitude)}, ${e(details.place.longitude)}</p>
  ${details.menus.map(menu => `<p>${e(menu.name)} · 메뉴 ID <code>${e(menu.id)}</code> · 근거 ${e(menu.evidence_id)}</p>`).join('')}
  ${details.evidence.map(item => `<div class="card"><strong>${e(item.provider)} · ${e(fieldLabels[item.field] ?? item.field)} · ${e(observationLabels[item.status] ?? item.status)} · ${e(modeLabels[item.mode] ?? item.mode)} · ${e(matchLabels[item.match_status] ?? item.match_status)}</strong><p>원문 ${e(JSON.stringify(item.raw_value))}</p><p>조회 ${e(item.retrieved_at)} / 공급자 기준일 ${e(item.provider_updated_at ?? '미확인')}</p>${evidenceLink(item.source_url)}</div>`).join('') || '<p>등록된 출처가 없습니다.</p>'}
  </details>`);
}
import {requestJson} from './api.js';
import {setSelectedPlace,getSelectedPlace,getSnapshot} from './state.js';
import {renderPlaceMap} from './map.js';
import {displayPlan,sameTarget} from './plan.js';
let detailRequestSequence = 0;
export async function selectPlace(roomId,ref) {
  const requestSequence = ++detailRequestSequence;
  const target = structuredClone(displayPlan(getSnapshot() ?? {})?.confirmation_target ?? null);
  setSelectedPlace(ref);
  html('place','<p role="status">선택한 장소 정보를 불러오는 중…</p>');
  renderPlaceMap(null);
  const result = await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/places/' + encodeURIComponent(ref))
    .then(details => ({details}),error => ({error}));
  if (requestSequence !== detailRequestSequence) return;
  if (getSnapshot()?.room_id !== roomId || getSelectedPlace() !== ref) return;
  const currentTarget = displayPlan(getSnapshot() ?? {})?.confirmation_target ?? null;
  if (target !== currentTarget && !sameTarget(target,currentTarget)) return;
  const {details} = result;
  if (!details) {
    html('place', `<p role="status">선택한 장소 정보를 불러오지 못했어요.</p>
      <button type="button" data-place="${e(ref)}">장소 정보 다시 시도</button>`);
    throw 'error' in result ? result.error : new Error('장소 조회 결과가 없습니다.');
  }
  renderPlace(details); renderPlaceMap(details.place);
}
