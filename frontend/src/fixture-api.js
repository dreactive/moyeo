import initial from '../fixtures/room-snapshot.json' with {type:'json'};
import {fixturePlaces,resetFixturePlaces} from './fixture-places.js';
import {clearFixtureSession,readFixtureSession,readStoredFixtureSession,saveFixtureSession} from './fixture-session.js';

export const fixtureRoom = structuredClone(initial);
let fixtureUser = {id:'u1',name:'참가자1',email:'u1@fixture.test'};
export function setFixtureUser(id) {
  fixtureUser = {id,name:'참가자' + id.slice(1),email:id + '@fixture.test'};
  persistFixture();
  return fixtureUser;
}
export const getFixtureUser = () => fixtureUser;
let fixtureAuthenticated = false;
let lastFixtureRecord = null;
let fixtureScenario = 'initial';

function persistFixture() {
  if (!fixtureAuthenticated) return;
  if (globalThis.sessionStorage && readStoredFixtureSession() !== lastFixtureRecord) return;
  lastFixtureRecord = saveFixtureSession({authenticated:fixtureAuthenticated,userId:fixtureUser.id,snapshot:fixtureRoom,scenario:fixtureScenario});
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isRecordList(rows) {
  return Array.isArray(rows) && rows.every(isRecord);
}

function isSavedTrip(config) {
  return isRecordList(config?.fixed_costs)
    && Object.entries(initial.config).every(([key, value]) => ['start_date','end_date','per_person_budget_krw'].includes(key) || typeof config[key] === typeof value)
    && [config.start_date,config.end_date].every(date => date === null || (typeof date === 'string' && Number.isFinite(Date.parse(date))))
    && (config.per_person_budget_krw === null || (Number.isInteger(config.per_person_budget_krw) && config.per_person_budget_krw >= 0));
}

function isSavedDay(day) {
  return typeof day.date === 'string'
    && isRecordList(day.route_legs)
    && isRecordList(day.visits)
    && day.visits.every(visit => typeof visit.place_ref === 'string' && Array.isArray(visit.assumptions));
}

function isSavedCost(cost) {
  return cost === null || (
    isRecordList(cost?.lines)
    && [cost.per_person_krw,cost.paid_by_user_krw,cost.remaining_budget_krw,cost.planned_balance_krw].every(isRecord)
  );
}

function isSavedPlan(plan) {
  return plan === null || (
    isRecordList(plan?.days) && plan.days.every(isSavedDay)
    && isRecordList(plan.item_snapshots)
    && Array.isArray(plan.selected_item_ids)
    && Array.isArray(plan.blocking_conflict_ids)
    && isSavedCost(plan.cost)
  );
}

function hasSavedCardLists({items,constraints,questions,conflicts}) {
  return items.every(item => [item.source_message_ids,item.conflict_ids,item.supporter_ids].every(Array.isArray))
    && constraints.every(item => Array.isArray(item.source_message_ids))
    && questions.every(item => Array.isArray(item.related_item_ids))
    && conflicts.every(item => isRecordList(item.options));
}

function isSavedFixture(saved) {
  const snapshot = saved.snapshot;
  return saved.authenticated === true && snapshot?.room_id === initial.room_id
    && initial.members.some(member => member.user_id === saved.userId)
    && Object.keys(scenarios).includes(saved.scenario)
    && isSavedTrip(snapshot.config)
    && Object.entries(initial).every(([key, value]) => Object.hasOwn(snapshot, key)
      && (!Array.isArray(value) || isRecordList(snapshot[key])))
    && snapshot.members.every(member => typeof member.name === 'string' && typeof member.user_id === 'string')
    && Number.isInteger(snapshot.seq)
    && isRecord(snapshot.agent_status)
    && isRecord(snapshot.versions)
    && snapshot.messages.every(message => typeof message.author_id === 'string')
    && hasSavedCardLists(snapshot)
    && [snapshot.current_plan,snapshot.review_plan,snapshot.confirmed_plan].every(isSavedPlan);
}

function hydrateFixture() {
  if (!globalThis.sessionStorage) return;
  const stored = readStoredFixtureSession();
  if (stored === lastFixtureRecord) return;
  lastFixtureRecord = stored;
  fixtureAuthenticated = false;
  const saved = readFixtureSession(stored);
  if (saved === null) {
    resetFixtureMemory();
    lastFixtureRecord = readStoredFixtureSession();
    return;
  }
  if (!isSavedFixture(saved)) {
    resetFixtureSession();
    return;
  }
  setFixtureUser(saved.userId);
  fixtureAuthenticated = true;
  Object.assign(fixtureRoom, saved.snapshot);
  fixtureRoom.deleted = saved.snapshot.deleted === true;
  setScenarioPlaces(saved.scenario);
}
function resetFixtureMemory() {
  fixtureAuthenticated = false;
  setFixtureUser('u1');
  Object.assign(fixtureRoom, structuredClone(initial));
  fixtureRoom.deleted = false;
  setScenarioPlaces('initial');
}

export function resetFixtureSession() {
  resetFixtureMemory();
  lastFixtureRecord = null;
  clearFixtureSession();
}

function requireFixtureLogin() {
  if (!fixtureAuthenticated) throw Object.assign(new Error('fixture 로그인이 필요합니다.'), {status:401});
}

export async function requestFixture(path, {method = 'GET',body,headers} = {}) {
  const parts = new URL(path,'http://fixture').pathname.split('/').map(decodeURIComponent);
  if (parts[2] === 'dev') {
    if (headers?.['X-Dev-Token'] !== 'fixture-dev') throw new Error('fixture 접근 거부 (403)');
    const runId = new URL(path,'http://fixture').searchParams.get('run_id');
    return {runs:!runId || runId === trace.run_id ? [structuredClone(trace)] : []};
  }
  hydrateFixture();
  if (parts[2] === 'auth') {
    if (method === 'POST' && parts[3] === 'logout') {
      resetFixtureSession();
      return {ok:true};
    }
    if (method === 'POST' && ['login','register'].includes(parts[3])) {
      fixtureAuthenticated = true;
      persistFixture();
    }
    requireFixtureLogin();
    return structuredClone(fixtureUser);
  }
  if (parts[2] === 'rooms') requireFixtureLogin();
  if (parts[2] === 'rooms' && parts.length === 3 && method === 'GET') {
    return {rooms:fixtureRoom.deleted ? [] : [fixtureRoomSummary()]};
  }
  if (parts[2] === 'rooms' && parts.length === 3 && method === 'POST') fixtureRoom.deleted = false;
  if (parts[2] === 'rooms' && parts.length >= 4 && fixtureRoom.deleted) {
    throw Object.assign(new Error('fixture 방을 찾을 수 없어요.'), {status:404});
  }
  if (parts[2] === 'rooms' && parts.length === 4 && method === 'DELETE') {
    if (fixtureUser.id !== fixtureRoom.members[0]?.user_id) throw Object.assign(new Error('방장만 삭제할 수 있어요.'), {status:403});
    fixtureRoom.deleted = true;
    persistFixture();
    emitFixture('onRoomDeleted',{room_id:fixtureRoom.room_id});
    return {ok:true};
  }
  if (parts[4] === 'members' && method === 'POST') {
    const member = initial.members.find(member => member.user_id + '@fixture.test' === String(body.email).trim().toLowerCase());
    if (!member) throw Object.assign(new Error('가입된 fixture 사용자가 아니에요.'), {status:404});
    return {...member,added:false};
  }
  if (parts[4] === 'places') return structuredClone(fixturePlaces.get(parts[5]));
  if (parts[2] === 'rooms' && parts.length === 4 && method === 'GET') {
    if (parts[3] !== fixtureRoom.room_id) throw Object.assign(new Error('fixture 방을 찾을 수 없어요.'), {status:404});
    return structuredClone(fixtureRoom);
  }
  if (parts[2] === 'rooms' && parts[3] === 'join') {
    if (body.invite_code !== 'FIXTURE') throw new Error('fixture 초대 코드는 FIXTURE입니다.');
    return replayScenario('initial');
  }
  if (parts[2] === 'rooms' && (parts.length === 3 || parts[4] === 'trip')) {
    fixtureRoom.config = {...fixtureRoom.config,...body};
    delete fixtureRoom.config.title;
    if (body.title) fixtureRoom.title = body.title;
    fixtureRoom.current_plan = fixtureRoom.review_plan = fixtureRoom.active_target = null;
    fixtureRoom.confirmations = [];
    fixtureRoom.seq++;
    persistFixture();
    return structuredClone(fixtureRoom);
  }
  if (parts[4] === 'messages') {
    if (method === 'POST') {
      const message = {id:crypto.randomUUID(),room_id:fixtureRoom.room_id,seq:++fixtureRoom.seq,author_id:fixtureUser.id,text:body.text,created_at:new Date().toISOString()};
      fixtureRoom.messages.push(message);
      persistFixture();
      emitFixture('onMessage',{room_id:fixtureRoom.room_id,seq:fixtureRoom.seq,message});
      return structuredClone(message);
    }
    if (parts[5]) return structuredClone(fixtureRoom.messages.find(message => message.id === parts[5]));
    return {messages:structuredClone(fixtureRoom.messages),last_seq:fixtureRoom.seq};
  }
  if (parts[4] === 'questions' || parts[4] === 'constraints') {
    const item = fixtureRoom[parts[4]].find(item => item.id === parts[5]);
    if (!item || (item.owner_id && item.owner_id !== fixtureUser.id)) throw new Error('fixture: 소유자만 응답할 수 있습니다.');
    if (parts[4] === 'questions') {
      Object.assign(item,{status:'answered',answer:body.value,answered_by:fixtureUser.id});
      applyFixtureAnswer(item);
    } else if (method === 'PATCH') item.value = body.value;
    else item.status = 'confirmed';
    fixtureRoom.seq++;
    persistFixture();
    return method === 'PATCH' ? structuredClone(item) : structuredClone(fixtureRoom);
  }
  if (parts[4] === 'plan') {
    if (parts[5] === 'activate') return replayScenario('activated');
    if (parts[5] === 'withdraw') {
      if (!sameTarget(body.target,fixtureRoom.active_target)) throw new Error('fixture: 오래된 대상입니다.');
      fixtureRoom.confirmations = fixtureRoom.confirmations.filter(vote => vote.user_id !== fixtureUser.id);
      fixtureRoom.seq++;
      persistFixture();
      return structuredClone(fixtureRoom);
    }
    const plan = fixtureRoom.review_plan ?? fixtureRoom.current_plan;
    if (plan?.validation !== 'ready' || !sameTarget(body.target,plan.confirmation_target)) throw new Error('fixture: 오래되거나 확인 불가능한 대상입니다.');
    return replayScenario((body.target.plan_revision === 2 ? 'confirm2-' : 'confirm-') + fixtureUser.id);
  }
  if (parts[4] === 'conflicts' || parts[4] === 'agent-runs') {
    replayScenario(parts[4] === 'conflicts' ? 'selected' : 'ready');
    return {run_id:'run-fixture-selected',base_versions:structuredClone(fixtureRoom.versions)};
  }
  throw new Error('fixture 미지원 요청: ' + method + ' ' + path);
}

function fixtureRoomSummary() {
  const last = fixtureRoom.messages.at(-1);
  const plan = fixtureRoom.review_plan ?? fixtureRoom.current_plan;
  const target = plan?.confirmation_target;
  const current = target && ['participant_version','constraint_version','evidence_version'].every(key => fixtureRoom.versions[key] === target[key]);
  const official = current && sameTarget(fixtureRoom.confirmed_plan?.confirmation_target,target);
  return {
    room_id:fixtureRoom.room_id,title:fixtureRoom.title,invite_code:fixtureRoom.invite_code,
    owner_id:fixtureRoom.members[0]?.user_id,is_owner:fixtureUser.id === fixtureRoom.members[0]?.user_id,
    region:fixtureRoom.config.region,start_date:fixtureRoom.config.start_date,end_date:fixtureRoom.config.end_date,
    members:structuredClone(fixtureRoom.members),agent_state:fixtureRoom.agent_status.state,
    plan_stage:official ? 'confirmed' : plan ? 'draft' : 'empty',plan_revision:plan?.plan_revision ?? null,
    last_message:last ? {...last,author_name:fixtureRoom.members.find(member => member.user_id === last.author_id)?.name,mine:last.author_id === fixtureUser.id} : null
  };
}
const subscriptions = new Map();
export function subscribeFixture(roomId, handlers) {
  subscriptions.set(handlers,roomId);
  return () => subscriptions.delete(handlers);
}
export function emitFixture(name, data) {
  subscriptions.forEach((roomId,handlers) => {
    if (roomId === data.room_id) handlers[name]?.(structuredClone(data));
  });
}
import scenarios from '../fixtures/scenarios.json' with {type:'json'};
export {scenarios};

export const getFixtureScenario = () => fixtureScenario;

function setScenarioPlaces(key) {
  fixtureScenario = key;
  resetFixturePlaces();
  scenarios[key].places?.forEach(details => fixturePlaces.set(details.place.id, structuredClone(details)));
}

export function replayScenario(key) {
  const next = scenarios[key];
  const seq = fixtureRoom.seq + 1;
  Object.assign(fixtureRoom,structuredClone(next.snapshot),{seq});
  setScenarioPlaces(key);
  persistFixture();
  emitFixture('onRoomUpdated',{room_id:fixtureRoom.room_id,seq,changed:['fixture_scenario']});
  return structuredClone(fixtureRoom);
}




function applyFixtureAnswer(question) {
  const value = question.answer;
  const visit = fixtureRoom.current_plan?.days.flatMap(day => day.visits).find(visit => visit.item_id === question.target_ref);
  if (question.field === 'visit_duration' && visit) visit.stay_minutes = value.stay_minutes;
  if (question.field === 'menu_selection' && visit) { visit.selected_menu_ids = [value.menu_id]; visit.assumptions = [JSON.stringify(value)]; }
  if (question.field === 'constraint_value') fixtureRoom.constraints.find(item => item.id === question.target_ref).value = value.value;
  fixtureRoom.agent_status = {run_id:'run-fixture-answer',state:'needs_input',label:'fixture 응답 저장 · 실제 재계획은 live에서 검증'};
  if (['origin','destination','lodging'].includes(question.field)) fixtureRoom.config[question.field] = question.answer;
}

import trace from '../fixtures/run-trace.json' with {type:'json'};


import {sameTarget} from './plan.js';
