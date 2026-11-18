export const displayPlan = snapshot => snapshot.review_plan ?? snapshot.current_plan;
const targetKeys = ['participant_version','constraint_version','evidence_version','plan_revision','content_hash'];
export const sameTarget = (a,b) => !!a && !!b && targetKeys.every(key => a[key] === b[key]);
import {html,escapeHtml as e} from './ui.js';
import {getUser} from './state.js';
export function planContent(plan) {
  if (!plan) return '<p>여행안이 아직 없습니다.</p>';
  const titles = new Map(plan.item_snapshots.map(item => [item.id,item.title]));
  return `<p>revision ${e(plan.plan_revision)} · 검증 ${e(plan.validation)}</p>
  <p>차단 충돌: ${e(plan.blocking_conflict_ids.join(', ') || '없음')}</p>
  <p class="muted">확인 대상 ${e(JSON.stringify(plan.confirmation_target))}</p>
  <ul>${plan.item_snapshots.map(item => `<li>${e(item.title)} · v${e(item.item_version)}</li>`).join('')}</ul>
  ${plan.days.map(day => `<h3>${e(day.date)}</h3><ol>${day.visits.map(visit => `<li>${e(titles.get(visit.item_id) ?? visit.place_ref)} ${e(visit.start_at)} ~ ${e(visit.end_at)} · ${visit.stay_minutes}분 · ${e(visit.assumptions.join(' / '))}</li>`).join('')}</ol>`).join('')}`;
}
function confirmationNote(plan,currentBasis,pendingHard) {
  if (!plan) return '대화에서 방문하고 싶은 곳을 알려주세요.';
  if (!currentBasis) return '여행 입력이 바뀌었어요. 최신 여행안을 확인해 주세요.';
  if (plan.blocking_conflict_ids.length || plan.validation === 'conflict') return '<a href="#conflicts">해결할 충돌 보기</a>';
  if (pendingHard) return '<a href="#constraints">본인 확인이 필요한 필수 조건 보기</a>';
  return plan.validation === 'ready' ? '' : '<a href="#questions">추가 입력 확인하기</a>';
}
export function renderPlan(snapshot) {
  const plan = displayPlan(snapshot);
  const target = plan?.confirmation_target;
  const currentBasis = hasCurrentBasis(snapshot,target);
  const currentVotes = currentBasis ? snapshot.confirmations : [];
  const votes = new Map(currentVotes.filter(vote => sameTarget(vote.target,target)).map(vote => [vote.user_id,vote.stance]));
  const pendingHard = snapshot.constraints.some(item => item.kind === 'hard' && item.status === 'needs_owner_confirmation');
  const count = snapshot.members.filter(member => votes.get(member.user_id) === 'confirm').length;
  const official = currentBasis && sameTarget(target,snapshot.confirmed_plan?.confirmation_target);
  const status = official ? '공식 확정' : count && count === snapshot.members.length ? '모두 동의 · 확정 확인 중' : '검토 중';
  const members = snapshot.members.map(({user_id,name}) => {
    const voted = votes.get(user_id) === 'confirm';
    return `<li class="${voted ? 'has-vote' : ''}">${e(name)} · ${voted ? '동의' : '아직'}</li>`;
  }).join('');
  const canWithdraw = sameTarget(snapshot.active_target,target) && votes.get(getUser()?.id) === 'confirm';
  const note = confirmationNote(plan,currentBasis,pendingHard);
  html('plan', `<h3>${snapshot.review_plan ? '검토 중인 안' : '최신 초안'}</h3>${planContent(plan)}
  <p class="consensus-status">같은 여행안 확인 ${count}/${snapshot.members.length} · ${status}</p>
  <ul class="member-votes">${members}</ul>
  ${note ? `<p class="muted">${note}</p>` : ''}
  ${canWithdraw ? '<button data-plan="withdraw">내 동의 철회</button>'
    : `<button data-plan="confirm" ${note ? 'disabled' : ''}>나도 동의하기</button>`}
  ${snapshot.review_plan && !sameTarget(snapshot.current_plan?.confirmation_target,plan?.confirmation_target) ? '<button data-plan="activate">새 안으로 전환</button>' : ''}`);
  html('confirmed-plan', '<h3>이전/현재 확정 스냅샷</h3>' + planContent(snapshot.confirmed_plan));
}
const basisKeys = ['participant_version','constraint_version','evidence_version'];
export const hasCurrentBasis = (snapshot,target) => !!target && basisKeys.every(key => snapshot.versions[key] === target[key]);
