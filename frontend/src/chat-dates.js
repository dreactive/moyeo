// Day grouping for the chat: dates follow Asia/Seoul like the rest of the app.
const keyFormat = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'});
const weekdays = ['일','월','화','수','목','금','토'];
export function dayKey(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? String(iso ?? '').slice(0,10) : keyFormat.format(date);
}
export function dayLabel(key) {
  const [year,month,day] = key.split('-').map(Number);
  const weekday = weekdays[new Date(Date.UTC(year,month - 1,day)).getUTCDay()];
  return `${year}년 ${month}월 ${day}일 ${weekday}요일`;
}
export function mergeMessages(...lists) {
  const byId = new Map();
  lists.flat().forEach(message => byId.set(message.id,message));
  return [...byId.values()].sort((a,b) => (a.seq ?? 0) - (b.seq ?? 0));
}
export function groupByDay(messages) {
  const groups = [];
  for (const message of messages) {
    const key = dayKey(message.created_at);
    if (groups.at(-1)?.key !== key) groups.push({key,label:dayLabel(key),messages:[]});
    groups.at(-1).messages.push(message);
  }
  return groups;
}
// Month grid for the date picker: Sunday-first weeks, null for padding cells.
export function monthGrid(year,month) {
  const first = new Date(Date.UTC(year,month - 1,1)).getUTCDay();
  const days = new Date(Date.UTC(year,month,0)).getUTCDate();
  const cells = Array.from({length:first},() => null).concat(Array.from({length:days},(_,index) => index + 1));
  while (cells.length % 7) cells.push(null);
  return Array.from({length:cells.length / 7},(_,week) => cells.slice(week * 7,week * 7 + 7));
}
export const monthKey = key => key.slice(0,7);
export function shiftMonth(month,delta) {
  const [year,value] = month.split('-').map(Number);
  const date = new Date(Date.UTC(year,value - 1 + delta,1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2,'0')}`;
}
