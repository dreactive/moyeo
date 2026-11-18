export const displayPlan = snapshot => snapshot.review_plan ?? snapshot.current_plan;
const targetKeys = ['participant_version','constraint_version','evidence_version','plan_revision','content_hash'];
export const sameTarget = (a,b) => !!a && !!b && targetKeys.every(key => a[key] === b[key]);
import {html,escapeHtml as e} from './ui.js';
export function planContent(plan) {
  if (!plan) return '<p>여행안이 아직 없습니다.</p>';
  return `<p>revision ${e(plan.plan_revision)} · 검증 ${e(plan.validation)}</p>
  <p>차단 충돌: ${e(plan.blocking_conflict_ids.join(', ') || '없음')}</p>
  <p class="muted">확인 대상 ${e(JSON.stringify(plan.confirmation_target))}</p>
  <ul>${plan.item_snapshots.map(item => `<li>${e(item.title)} · v${e(item.item_version)}</li>`).join('')}</ul>
  ${plan.days.map(day => `<h3>${e(day.date)}</h3><ol>${day.visits.map(visit => `<li><button data-place="${e(visit.place_ref)}">${e(visit.place_ref)}</button> ${e(visit.start_at)} ~ ${e(visit.end_at)} · ${visit.stay_minutes}분 · ${e(visit.assumptions.join(' / '))}</li>`).join('')}</ol>`).join('')}`;
}
export function renderPlan(snapshot) {
  const plan = displayPlan(snapshot);
  const target = plan?.confirmation_target;
  const currentVotes = hasCurrentBasis(snapshot,target) ? snapshot.confirmations : [];
  const votes = new Map(currentVotes.filter(vote => sameTarget(vote.target,target)).map(vote => [vote.user_id,vote.stance]));
  const pendingHard = snapshot.constraints.some(item => item.kind === 'hard' && item.status === 'needs_owner_confirmation');
  const count = snapshot.members.filter(member => votes.get(member.user_id) === 'confirm').length;
  const official = hasCurrentBasis(snapshot,target) && sameTarget(target,snapshot.confirmed_plan?.confirmation_target);
  const status = official ? '공식 확정' : count && count === snapshot.members.length ? '모두 동의 · 확정 확인 중' : '검토 중';
  const members = snapshot.members.map(({user_id,name}) => {
    const voted = votes.get(user_id) === 'confirm';
    return `<li class="${voted ? 'has-vote' : ''}">${e(name)} · ${voted ? '동의' : '아직'}</li>`;
  }).join('');
  html('plan', `<h3>${snapshot.review_plan ? '검토 중인 안' : '최신 초안'}</h3>${planContent(plan)}
  <p class="consensus-status">같은 여행안 확인 ${count}/${snapshot.members.length} · ${status}</p>
  <ul class="member-votes">${members}</ul>
  <button data-plan="confirm" ${!plan || !hasCurrentBasis(snapshot,plan.confirmation_target) || plan.validation !== 'ready' || plan.blocking_conflict_ids.length || pendingHard ? 'disabled' : ''}>전체 여행안 확인</button>
  <button data-plan="withdraw" ${!plan ? 'disabled' : ''}>내 확인 철회</button>
  ${snapshot.review_plan && !sameTarget(snapshot.current_plan?.confirmation_target,plan?.confirmation_target) ? '<button data-plan="activate">새 안으로 전환</button>' : ''}`);
  html('confirmed-plan', '<h3>이전/현재 확정 스냅샷</h3>' + planContent(snapshot.confirmed_plan));
}
const basisKeys = ['participant_version','constraint_version','evidence_version'];
export const hasCurrentBasis = (snapshot,target) => !!target && basisKeys.every(key => snapshot.versions[key] === target[key]);
