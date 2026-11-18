import {hasCurrentBasis,isOfficialPlan} from './plan.js';
import {escapeHtml as e} from './ui.js';

export const agreementLabels = {mentioned:'언급됨',supported:'과반 지지',confirmed:'✓ 확정'};

export function itemAgreement(snapshot,item,plan) {
  if (!item) return null;
  const matches = entry => entry.id === item.id && entry.item_version === item.item_version;
  const official = snapshot.confirmed_plan;
  const confirmed = isOfficialPlan(snapshot,plan) && plan.selected_item_ids.includes(item.id)
    && official.selected_item_ids.includes(item.id) && plan.item_snapshots.some(matches)
    && official.item_snapshots.some(matches);
  const support = new Set(item.supporter_ids).size;
  const opponents = new Set(item.opponent_ids).size;
  const total = snapshot.members.length;
  const state = confirmed ? 'confirmed' : item.state === 'confirmed'
    ? (support >= item.support_threshold ? 'supported' : 'mentioned') : item.state;
  const label = confirmed ? `✓ 확정 v${plan.plan_revision}` : agreementLabels[state];
  const partial = state !== 'confirmed' && support > 0 && support < item.support_threshold;
  const counts = `${partial ? '일부 지지' : '지지'} ${support}/${total} · 반대 ${opponents}명`;
  return {state,label,counts,
    version:item.item_version,conflict:!!item.conflict_ids?.length};
}

export function planItemAgreements(snapshot,plan) {
  if (!hasCurrentBasis(snapshot,plan?.confirmation_target)) return new Map();
  const current = new Map((snapshot.items ?? []).map(item => [item.id,item]));
  return new Map((plan.item_snapshots ?? []).flatMap(entry => {
    const item = current.get(entry.id);
    return item?.item_version === entry.item_version ? [[entry.id,itemAgreement(snapshot,item,plan)]] : [];
  }));
}

export function agreementMarkup(agreement) {
  if (!agreement) return '<small class="muted">표시 항목의 동의 기록 미확인</small>';
  return `<span class="agreement-badge ${agreement.state}">${e(agreement.label)}</span>
    ${agreement.conflict ? '<strong class="badge">! 충돌</strong>' : ''}
    <small class="agreement-counts">현재 항목 v${e(agreement.version)} · ${e(agreement.counts)}</small>`;
}

export const agreementLegend = `<p class="muted agreement-legend">지도 방문 번호와 동의 상태
  ${['mentioned','supported','confirmed'].map(state => `<span class="agreement-badge ${state}">${agreementLabels[state]}</span>`).join('')}
  <span class="agreement-badge">동의 미확인</span> · 경로선은 조회된 구간</p>`;
