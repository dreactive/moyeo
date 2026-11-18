import {html,escapeHtml as e,money} from './ui.js';
export const safeUrl = value => /^https?:\/\//i.test(value ?? '') ? value : '';
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
  <h3>메뉴</h3>${details.menus.map(menu => `<p>${e(menu.name)} · ${menu.price_krw == null ? e(menu.price_text || '미확인') + ' (금액 미확인)' : money(menu.price_krw)} · ${e(menu.serving_basis ?? '제공 단위 미확인')} · ${e(menu.evidence_id)}</p>`).join('') || '<p>메뉴 미등록 · 가격 미확인</p>'}
  <details class="card-details"><summary>장소 정보 출처</summary>
  <p>좌표 ${e(details.place.latitude)}, ${e(details.place.longitude)}</p>
  ${details.evidence.map(item => `<div class="card"><strong>${e(item.provider)} · ${e(item.field)} · ${e(item.status)} · ${e(item.mode)} · ${e(item.match_status)}</strong><p>원문 ${e(JSON.stringify(item.raw_value))}</p><p>조회 ${e(item.retrieved_at)} / 공급자 기준일 ${e(item.provider_updated_at ?? '미확인')}</p>${evidenceLink(item.source_url)}</div>`).join('') || '<p>등록된 출처가 없습니다.</p>'}
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
  const details = await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/places/' + encodeURIComponent(ref));
  if (requestSequence !== detailRequestSequence) return;
  if (getSnapshot()?.room_id !== roomId || getSelectedPlace() !== ref) return;
  const currentTarget = displayPlan(getSnapshot() ?? {})?.confirmation_target ?? null;
  if (target !== currentTarget && !sameTarget(target,currentTarget)) return;
  if (!details) throw new Error('장소 조회 결과가 없습니다.');
  renderPlace(details); renderPlaceMap(details.place);
}
