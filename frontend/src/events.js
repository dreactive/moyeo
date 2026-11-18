import {getDataMode} from './api.js';
import {subscribeFixture} from './fixture-api.js';
let closeCurrent = () => {};
const names = {'message.created':'onMessage','room.updated':'onRoomUpdated','agent.status':'onAgentStatus','plan.confirmed':'onPlanConfirmed','room.deleted':'onRoomDeleted'};
export function openRoomEvents(roomId, handlers) {
  closeCurrent();
  if (getDataMode() === 'fixture') return closeCurrent = subscribeFixture(roomId,handlers);
  const source = new EventSource('/api/rooms/' + encodeURIComponent(roomId) + '/events');
  let active = true;
  Object.entries(names).forEach(([event,handler]) => source.addEventListener(event, message => {
    if (active) handlers[handler]?.(JSON.parse(message.data));
  }));
  source.onopen = () => { if (active) handlers.onReconnect?.(); };
  closeCurrent = () => { active = false; source.close(); };
  return closeCurrent;
}
