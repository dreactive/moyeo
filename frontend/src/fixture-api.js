import initial from '../fixtures/room-snapshot.json' with {type:'json'};
import {fixturePlaces} from './fixture-places.js';
export const fixtureRoom = structuredClone(initial);
let fixtureUser = {id:'u1',name:'참가자1',email:'u1@fixture.test'};
export const setFixtureUser = id => { fixtureUser = {id,name:'참가자' + id.slice(1),email:id + '@fixture.test'}; return fixtureUser; };
export const getFixtureUser = () => fixtureUser;
export async function requestFixture(path, {method = 'GET',body} = {}) {
  const parts = new URL(path,'http://fixture').pathname.split('/').map(decodeURIComponent);
  if (parts[2] === 'auth') return parts[3] === 'logout' ? {ok:true} : structuredClone(fixtureUser);
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
  if (parts[4] === 'plan') {
    if (parts[5] === 'activate') return replayScenario('activated');
    if (parts[5] === 'withdraw') return replayScenario('ready');
    return replayScenario('confirm-' + fixtureUser.id);
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
export function replayScenario(key) {
  const next = scenarios[key];
  const seq = fixtureRoom.seq + 1;
  Object.assign(fixtureRoom,structuredClone(next.snapshot),{seq});
  next.places?.forEach(details => fixturePlaces.set(details.place.id,structuredClone(details)));
  emitFixture('onRoomUpdated',{room_id:fixtureRoom.room_id,seq,changed:['fixture_scenario']});
  return structuredClone(fixtureRoom);
}



