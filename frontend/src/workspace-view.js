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
