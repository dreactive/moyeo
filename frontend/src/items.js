import {html,escapeHtml as e} from './ui.js';
import {displayPlan,sameTarget} from './plan.js';
import {getUser} from './state.js';
const labels = {mentioned:'언급됨',supported:'다수 지지',confirmed:'확정'};
export const sourceLinks = ids => ids.map(id => `<button data-message="${e(id)}">근거 ${e(id)}</button>`).join('');
export function renderItems(snapshot) {
  const plan = displayPlan(snapshot);
  html('items', snapshot.items.map(item => {
    const confirmed = item.state === 'confirmed' && item.included_in_plan && sameTarget(plan?.confirmation_target,snapshot.confirmed_plan?.confirmation_target) && plan.item_snapshots.some(old => old.id === item.id && old.item_version === item.item_version);
    const state = item.state === 'confirmed' && !confirmed ? 'supported' : item.state;
    return `<div class="card ${e(state)}"><strong>${e(item.title)} · ${e(labels[state])}</strong>
    ${item.conflict_ids.length ? '<strong class="badge">! 충돌</strong>' : ''}
    <p>지지 ${item.supporter_ids.length}명 / 기준 ${item.support_threshold}명 · v${item.item_version}</p>${sourceLinks(item.source_message_ids)}</div>`;
  }).join('') || '<p>아직 공동 항목이 없습니다.</p>');
}
