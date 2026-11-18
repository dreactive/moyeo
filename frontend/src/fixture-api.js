import initial from '../fixtures/room-snapshot.json' with {type:'json'};
import {fixturePlaces,resetFixturePlaces} from './fixture-places.js';
import {clearFixtureSession,readFixtureSession,saveFixtureSession} from './fixture-session.js';

export const fixtureRoom = structuredClone(initial);
let fixtureUser = {id:'u1',name:'참가자1',email:'u1@fixture.test'};
export function setFixtureUser(id) {
  fixtureUser = {id,name:'참가자' + id.slice(1),email:id + '@fixture.test'};
  persistFixture();
  return fixtureUser;
}
export const getFixtureUser = () => fixtureUser;
let fixtureAuthenticated = false;
let fixtureSessionLoaded = false;
let fixtureScenario = 'initial';

function persistFixture() {
  if (!fixtureAuthenticated) return;
  saveFixtureSession({authenticated:fixtureAuthenticated,userId:fixtureUser.id,snapshot:fixtureRoom,scenario:fixtureScenario});
}

function isSavedFixture(saved) {
  const snapshot = saved.snapshot;
  return saved.authenticated === true && snapshot?.room_id === initial.room_id
    && initial.members.some(member => member.user_id === saved.userId)
    && Object.hasOwn(scenarios, saved.scenario)
    && Array.isArray(snapshot.config?.fixed_costs);
}

function hydrateFixture() {
  if (fixtureSessionLoaded) return;
  fixtureSessionLoaded = true;
  const saved = readFixtureSession();
  if (saved === null) return;
  if (!isSavedFixture(saved)) {
    clearFixtureSession();
    return;
  }
  setFixtureUser(saved.userId);
  fixtureAuthenticated = true;
  Object.assign(fixtureRoom, saved.snapshot);
  setScenarioPlaces(saved.scenario);
}
export function resetFixtureSession() {
  fixtureAuthenticated = false;
  fixtureSessionLoaded = true;
  setFixtureUser('u1');
  Object.assign(fixtureRoom, structuredClone(initial));
  setScenarioPlaces('initial');
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
  if (parts[4] === 'places') return structuredClone(fixturePlaces.get(parts[5]));
  if (parts.length === 4 && method === 'GET') return structuredClone(fixtureRoom);
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
    return method === 'PATCH' ? structuredClone(item) : structuredClone(fixtureRoom);
  }
  if (parts[4] === 'plan') {
    if (parts[5] === 'activate') return replayScenario('activated');
    if (parts[5] === 'withdraw') {
      if (!sameTarget(body.target,fixtureRoom.active_target)) throw new Error('fixture: 오래된 대상입니다.');
      fixtureRoom.confirmations = fixtureRoom.confirmations.filter(vote => vote.user_id !== fixtureUser.id);
      fixtureRoom.seq++;
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
