const rendered = new Map();
export function renderChanged(key,value,render) {
  const stamp = JSON.stringify(value);
  if (rendered.get(key) === stamp) return;
  if (render() !== false) rendered.set(key,stamp);
}
export function roomMeta(config) {
  const nights = Math.round((Date.parse(config.end_date) - Date.parse(config.start_date)) / 86400000);
  return `${config.start_date} — ${config.end_date} · ${nights}박 ${nights + 1}일 · ${config.region}`;
}
import {html,escapeHtml as e} from './ui.js';
export function renderOverview(snapshot) {
  html('room-heading',e(snapshot.title));
  html('room-meta',e(roomMeta(snapshot.config)));
  html('invite-code',e(snapshot.invite_code));
  html('members',snapshot.members.map(member => `<span class="member-avatar" title="${e(member.name)}">${e(member.name.slice(0,1))}</span>`).join('') + `<span class="member-count">${snapshot.members.length}명 참여</span>`);
}
const agentLabels = {idle:'여행 이야기를 기다리고 있어요',running:'조건과 동선을 검토하고 있어요',needs_input:'확인이 필요한 내용이 있어요',done:'여행안 검토가 끝났어요'};
export function renderAgentBanner(snapshot) {
  const status = snapshot.agent_status;
  const label = status.label === status.state || status.label === 'Ready' ? agentLabels[status.state] : status.label;
  const questions = snapshot.questions.filter(item => item.status === 'open').length;
  const conflicts = snapshot.conflicts.filter(item => item.status === 'open').length;
  html('agent',`<strong>${e(label)}</strong><p>확인 질문 ${questions}개 · 해결할 충돌 ${conflicts}개</p>`);
  const button = document.getElementById('replan');
  button.disabled = snapshot.agent_status.state === 'running' || button.dataset?.pending === 'true';
}
import {displayPlan} from './plan.js';
export const routeKey = (snapshot,date) => JSON.stringify([snapshot.room_id,displayPlan(snapshot)?.confirmation_target,snapshot.config,date]);
export function placeVisitDay(plan,ref,selected) {
  const contains = day => day.visits.some(visit => visit.place_ref === ref);
  return plan?.days.find(day => day.date === selected && contains(day)) ?? plan?.days.find(contains);
}
export function sharedRenderData({messages,agent_status,seq,...shared}) { return shared; }
