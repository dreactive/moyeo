export const displayPlan = snapshot => snapshot.review_plan ?? snapshot.current_plan;
const targetKeys = ['participant_version','constraint_version','evidence_version','plan_revision','content_hash'];
export const sameTarget = (a,b) => !!a && !!b && targetKeys.every(key => a[key] === b[key]);
export const isOfficialPlan = (snapshot,plan) => hasCurrentBasis(snapshot,plan?.confirmation_target)
  && sameTarget(plan.confirmation_target,snapshot.confirmed_plan?.confirmation_target);
export function planAgreement(snapshot,plan) {
  const target = plan?.confirmation_target;
  const currentBasis = hasCurrentBasis(snapshot,target);
  const votes = new Map((currentBasis ? snapshot.confirmations ?? [] : [])
    .filter(vote => sameTarget(vote.target,target)).map(vote => [vote.user_id,vote.stance]));
  const count = snapshot.members.filter(member => votes.get(member.user_id) === 'confirm').length;
  const official = isOfficialPlan(snapshot,plan);
  const status = official ? '공식 확정' : snapshot.review_plan ? '검토 중' : '초안';
  return {currentBasis,votes,count,official,status};
}
import {html,escapeHtml as e,clock,avatar} from './ui.js';
import {getUser} from './state.js';
const validationLabel = {ready:'검증 완료',needs_input:'추가 입력 필요',conflict:'충돌 해결 필요'};
export function planContent(plan,dated = true,interactive = false) {
  if (!plan) return '<p class="empty">여행안이 아직 없습니다.</p>';
  const nameOf = ref => plan.item_snapshots.find(item => item.place_ref === ref)?.title ?? ref;
  return `<p class="plan-meta"><span class="pill">revision ${e(plan.plan_revision)}</span> <span class="pill v-${e(plan.validation)}">검증 ${e(plan.validation)} · ${e(validationLabel[plan.validation] ?? '')}</span>
  <span class="muted">차단 충돌: ${e(plan.blocking_conflict_ids.join(', ') || '없음')}</span></p>
  <p class="muted small hash" title="${e(JSON.stringify(plan.confirmation_target))}">확인 대상 · 참가자 v${e(plan.confirmation_target.participant_version)} · 조건 v${e(plan.confirmation_target.constraint_version)} · 근거 v${e(plan.confirmation_target.evidence_version)} · 안 r${e(plan.confirmation_target.plan_revision)} · ${e(String(plan.confirmation_target.content_hash).slice(0,12))}…</p>
  <p class="included">${plan.item_snapshots.map(item => `<span class="chip">${e(item.title)} · v${e(item.item_version)}</span>`).join('')}</p>
  <div class="days">${plan.days.map((day,index) => `<div class="day"><h3>${index + 1}일차${dated ? ' · ' + e(day.date) : ' · 날짜 미정'}</h3><ol class="timeline">${day.visits.map(visit => `<li>${interactive ? `<button class="place-link" data-route-place="${e(visit.place_ref)}">${e(nameOf(visit.place_ref))}</button>` : e(nameOf(visit.place_ref))}<span class="time" title="${e(visit.start_at)} ~ ${e(visit.end_at)}">${clock(visit.start_at)} ~ ${clock(visit.end_at)}</span> <span class="muted">${visit.stay_minutes}분${visit.assumptions.length ? ' · ' + e(visit.assumptions.join(' / ')) : ''}</span></li>`).join('') || '<li class="muted">방문 일정 없음</li>'}</ol></div>`).join('')}</div>`;
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
  const {currentBasis,votes,count:confirmed,official} = planAgreement(snapshot,plan);
  const mine = votes.get(getUser()?.id) === 'confirm';
  const canWithdraw = sameTarget(snapshot.active_target,target) && mine;
  const pendingHard = snapshot.constraints.some(item => item.kind === 'hard' && item.status === 'needs_owner_confirmation');
  const warning = confirmationNote(plan,currentBasis,pendingHard);
  const status = official ? '공식 확정' : confirmed && confirmed === snapshot.members.length ? '모두 동의 · 확정 확인 중' : '검토 중';
  const headline = !plan ? '아직 여행안이 없어요'
    : official ? `v${e(plan.plan_revision)} 여행안이 확정됐어요`
    : `${snapshot.review_plan ? '검토 중인 안' : '최신 초안'} v${e(plan.plan_revision)}에 ${confirmed}명이 확인했어요`;
  const note = !plan ? '대화에서 가고 싶은 곳을 이야기하면 계획 도우미가 초안을 만들어요'
    : official ? '모두 확인하고 서버 검증을 통과했어요'
    : '전원 확인 및 서버 검증 후 확정돼요';
  html('plan', `<div class="confirm-bar${official ? ' is-confirmed' : ''}"><div class="confirm-text"><h3>${headline}</h3>
  <p class="muted">같은 여행안 확인 ${confirmed}/${snapshot.members.length} · ${status}</p>
  <p class="muted">${note}</p>${warning ? `<p class="muted">${warning}</p>` : ''}
  <p class="votes">${snapshot.members.map(member => `<span class="vote ${votes.get(member.user_id) === 'confirm' ? 'yes' : ''}">${avatar(member.name)}${e(member.name)} · ${{confirm:'동의',withdraw:'동의 철회'}[votes.get(member.user_id)] ?? '아직'}</span>`).join('')}</p></div>
  <div class="confirm-actions">${canWithdraw ? '<button class="ghost" data-plan="withdraw">내 동의 철회</button>' : `<button data-plan="confirm" ${warning ? 'disabled' : ''} class="primary lg">전체 여행안 확인</button>`}
  ${snapshot.review_plan && snapshot.current_plan && !sameTarget(snapshot.current_plan.confirmation_target,target) ? `<button data-plan="activate" class="accent">새 초안 v${e(snapshot.current_plan.plan_revision)}으로 전환</button>` : ''}</div></div>
  <details class="plan-detail" open><summary>여행안 상세 · 날짜별 일정</summary>${planContent(plan,!!snapshot.config.start_date,true)}</details>`);
  const archive = snapshot.confirmed_plan;
  html('confirmed-plan', archive ? `<details class="card-details"><summary>${official ? '확정안 보기' : '이전 확정안 보기'} · v${e(archive.plan_revision)}</summary>${planContent(archive)}</details>` : '');
}
const basisKeys = ['participant_version','constraint_version','evidence_version'];
export const hasCurrentBasis = (snapshot,target) => !!target && basisKeys.every(key => snapshot.versions?.[key] === target[key]);
