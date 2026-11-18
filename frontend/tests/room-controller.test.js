import test from 'node:test';
import assert from 'node:assert/strict';
import fixture from '../fixtures/room-snapshot.json' with {type:'json'};
import {runRoomTask} from '../src/room-errors.js';
import {setUser,applyRoomResponse,subscribeState} from '../src/state.js';
import {initMaps} from '../src/map.js';
import {withPending} from '../src/ui.js';

const elements = new Map();
globalThis.document = {
  addEventListener(){},querySelectorAll:() => [],querySelector:() => null,
  getElementById(id) { if (!elements.has(id)) elements.set(id,{}); return elements.get(id); }
};
globalThis.location = {search:'',assign(){}};
globalThis.fetch = async () => new Response(null,{status:401});
const room = await import('../src/room.js');
const {applySnapshot} = await import('../src/state.js');
await new Promise(setImmediate);

function workspaceDom(t) {
  const previous=globalThis.document;
  t.after(() => {globalThis.document=previous;});
  const nodes=new Map(),listeners=new Map();
  const node=id => {
    if (!nodes.has(id)) {
      let markup='';
      nodes.set(id,{dataset:{},children:[],scrollTop:0,scrollHeight:100,clientHeight:100,
        setAttribute(){},querySelectorAll:() => [],replaceChildren(...children){this.children=children;},
        get innerHTML(){return markup;},set innerHTML(value){
          markup=value;
          if (id === 'chat-count' || id === 'invite-box') {
            if (this.button) this.button.isConnected=false;
            this.button={isConnected:true,closest:() => null};
          }
        }});
    }
    return nodes.get(id);
  };
  globalThis.document={activeElement:null,querySelector:() => null,querySelectorAll:() => [],
    addEventListener:(type,listener) => listeners.set(type,listener),
    getElementById:id => id === 'setup-dialog' ? null : node(id)};
  return {node,listeners};
}

test('chat and trip focus changes keep participant and invite action targets connected', async t => {
  const {node,listeners}=workspaceDom(t);
  await initMaps({routeElement:node('route-map'),placeElement:node('place-map')});
  const snapshot={...fixture,room_id:'focusout-action-targets',messages:[],current_plan:null,review_plan:null};
  applySnapshot(snapshot);
  room.renderRoom(snapshot);
  await new Promise(setImmediate);
  room.bindRoomLifecycle();
  for (const source of ['message-text','trip-region']) {
    for (const id of ['chat-count','invite-box']) {
      const target=node(id).button;
      document.activeElement=target;
      listeners.get('focusout')({target:{id:source,closest:() => null},relatedTarget:target});
      await Promise.resolve();
      assert.equal(target.isConnected,true,`${source} to ${id} must preserve the pending click target`);
      assert.equal(node(id).button,target);
    }
  }
});

test('deferred questions refresh when leaving their form without replacing the pending action target', async t => {
  const {node,listeners}=workspaceDom(t);
  await initMaps({routeElement:node('route-map'),placeElement:node('place-map')});
  const initial={...fixture,room_id:'focusout-deferred-question',messages:[],current_plan:null,review_plan:null,questions:[]};
  applySnapshot(initial);
  room.renderRoom(initial);
  await new Promise(setImmediate);
  room.bindRoomLifecycle();
  const form={},input={closest:() => form},otherInput={closest:() => form};
  const changed={...initial,questions:[{id:'new-region',field:'region',text:'새 여행 지역을 정해 주세요',status:'open',owner_id:'u1'}]};
  applySnapshot(changed);
  document.activeElement=input;
  room.renderDecisionRegions(changed);
  assert.doesNotMatch(node('questions').innerHTML,/새 여행 지역/);
  document.activeElement=otherInput;
  listeners.get('focusout')({target:input,relatedTarget:otherInput});
  await Promise.resolve();
  assert.doesNotMatch(node('questions').innerHTML,/새 여행 지역/);
  const target=node('chat-count').button;
  document.activeElement=target;
  listeners.get('focusout')({target:otherInput,relatedTarget:target});
  await Promise.resolve();
  assert.match(node('questions').innerHTML,/새 여행 지역/);
  assert.equal(target.isConnected,true);
  assert.equal(node('chat-count').button,target);
});

test('a running agent keeps replan disabled after its pending request settles and the banner is unchanged', async t => {
  const {node}=workspaceDom(t);
  await initMaps({routeElement:node('route-map'),placeElement:node('place-map')});
  const initial={...fixture,room_id:'pending-replan-running',messages:[],current_plan:null,review_plan:null,
    agent_status:{state:'idle',label:'idle'}};
  applySnapshot(initial);
  room.renderRoom(initial);
  const button=node('replan');
  assert.equal(button.disabled,false);
  const running={...initial,agent_status:{state:'running',label:'동선을 검토하고 있어요'}};
  await withPending(button,async () => {
    applySnapshot(running);
    room.renderRoom(running);
    assert.equal(button.disabled,true);
  }).finally(() => room.renderRoom(running));
  assert.equal(button.dataset.pending,undefined);
  assert.equal(button.disabled,true);
});

test('a menu selection survives another room render after its options loaded', async () => {
  let writes=0;
  const select={dataset:{menuPlace:'test:menu-place'},isConnected:true,value:'',
    set innerHTML(markup) { writes++;this.value=markup.match(/value="([^"]*)"/)[1]; }
  };
  document.querySelectorAll=() => [select];
  globalThis.fetch=async () => Response.json({menus:[{id:'first',name:'첫 메뉴'},{id:'second',name:'둘째 메뉴'}]});
  await room.fillMenuChoices('menu-room');
  select.value='second';
  await room.fillMenuChoices('menu-room');
  assert.deepEqual([select.value,writes],['second',1]);
  document.querySelectorAll=() => [];
});

test('a decision update waits until the author leaves the focused form', () => {
  let writes=0;
  const original=document.getElementById;
  document.getElementById=() => ({set innerHTML(markup){writes++;}});
  document.activeElement={closest:() => ({})};
  const snapshot={...fixture,room_id:'focused-decision-test'};
  room.renderDecisionRegions(snapshot);
  assert.equal(writes,0);
  document.activeElement=null;
  room.renderDecisionRegions(snapshot);
  assert.equal(writes,4);
  document.getElementById=original;
});

test('restoring incoming fixed costs names every current member before room state changes', t => {
  const previousFormData=globalThis.FormData;
  const original=document.getElementById;
  t.after(() => {globalThis.FormData=previousFormData;document.getElementById=original;});
  globalThis.FormData=Map;
  const form=[];form.elements={title:{}};
  const rows={innerHTML:'',insertAdjacentHTML:(_,markup) => {rows.innerHTML+=markup;}};
  document.getElementById=id => id === 'trip' ? form : rows;
  applySnapshot({...fixture,room_id:'previous-room',members:[{user_id:'old',name:'이전 방 사람'}]});
  const incoming={...fixture,room_id:'incoming-room',config:{...fixture.config,fixed_costs:[{
    id:'hotel',category:'lodging',scope:'shared',description:'숙박',unit_price_krw:80000,quantity:1,paid:false,owner_id:'u2'
  }]}};
  room.restoreTrip(incoming);
  assert.match(rows.innerHTML,/<option value="u1"[^>]*>참가자1<\/option>/);
  assert.match(rows.innerHTML,/<option value="u2" selected>참가자2<\/option>/);
  assert.doesNotMatch(rows.innerHTML,/이전 방 사람/);
});

test('a membership SSE refresh updates cost target names without rebuilding an edited row', async t => {
  const previousDocument=globalThis.document;
  t.after(() => {globalThis.document=previousDocument;});
  const owner={value:'u2',dataset:{},innerHTML:''},amount={value:'123456'},description={value:'작성 중 숙박비'};
  const nodes=new Map();
  const node=id => {
    if (!nodes.has(id)) nodes.set(id,{dataset:{},children:[],scrollTop:40,scrollHeight:500,clientHeight:100,
      setAttribute(){},querySelectorAll:() => [],replaceChildren(...children){this.children=children;}});
    return nodes.get(id);
  };
  nodes.set('fixed-costs',{set innerHTML(markup){throw new Error('A membership render rebuilt a draft cost row');}});
  globalThis.document={activeElement:{...amount,closest:() => null},querySelector:() => null,
    querySelectorAll:selector => selector === '[name=cost_owner]' ? [owner] : [],
    getElementById:id => id === 'setup-dialog' ? null : node(id)};
  await initMaps({routeElement:node('route-map'),placeElement:node('place-map')});
  const initial={...fixture,room_id:'membership-sse',messages:[],current_plan:null,review_plan:null};
  applySnapshot(initial);
  const unsubscribe=subscribeState(room.renderRoom);t.after(unsubscribe);
  applyRoomResponse({...initial,seq:initial.seq+1,members:[...initial.members,{user_id:'joined',name:'새로 온 동행'}]},initial.room_id);
  await new Promise(setImmediate);
  assert.match(owner.innerHTML,/<option value="joined"[^>]*>새로 온 동행<\/option>/);
  assert.deepEqual([owner.value,amount.value,description.value],['u2','123456','작성 중 숙박비']);
});

test('an expired setup request closes its modal and keeps the relogin link accessible', async t => {
  const previous=document.getElementById;
  t.after(() => {document.getElementById=previous;setUser(null);});
  const dialog={open:true,close(){this.open=false;}};
  const error={};
  document.getElementById=id => id === 'setup-dialog' ? dialog : error;
  await runRoomTask(() => {throw Object.assign(new Error('expired'),{status:401});},{showError(){},expired:() => room.expireRoomSession?.()});
  assert.equal(dialog.open,false);
  assert.match(error.innerHTML,/href="\/login.html"/);
  setUser({id:'u1'});
  room.syncSetupDialog?.({...fixture,owner_id:'u1',config:{...fixture.config,region:'',per_person_budget_krw:null}});
  assert.equal(dialog.open,false);
});

test('the agent banner explains status without exposing an internal run identifier', t => {
  const previous=document.getElementById;
  t.after(() => {document.getElementById=previous;});
  const agent={},replan={dataset:{}};
  document.getElementById=id => id === 'agent' ? agent : replan;
  room.renderRoomAgent?.({...fixture,agent_status:{state:'running',label:'동선을 검토하고 있어요',run_id:'internal-run-123'}});
  assert.match(agent.innerHTML ?? '',/동선을 검토하고 있어요/);
  assert.doesNotMatch(agent.innerHTML,/internal-run-123/);
});

test('the new agent banner keeps request outcomes and current partial result links', t => {
  const previous=document.getElementById;
  t.after(() => {document.getElementById=previous;});
  const agent={},replan={dataset:{}};
  document.getElementById=id => id === 'agent' ? agent : replan;
  room.renderRoomAgent({...fixture,agent_status:{state:'waiting',label:'waiting'},
    agent_requests:[{request_id:'request-1',owner_id:'u1',status:'pending',evidence:{quote:'두 곳을 확인해 줘'},
      completed_refs:['fixture:place-a'],pending_refs:['fixture:place-b'],response:'첫 장소는 확인했어요',
      result_refs:['fixture:place-a','anchor:origin'],source_message_id:'m1'}],
    agent_results:{run_id:'partial-run',versions:fixture.versions,build_itinerary:{days:[]},calculate_costs:{}}});
  assert.match(agent.innerHTML,/아직 완료되지 않은 작업/);
  assert.match(agent.innerHTML,/요청별 진행 상태/);
  assert.match(agent.innerHTML,/완료 1곳 · 대기 1곳/);
  assert.match(agent.innerHTML,/첫 장소는 확인했어요/);
  assert.match(agent.innerHTML,/data-place="fixture:place-a"/);
  assert.doesNotMatch(agent.innerHTML,/data-place="anchor:origin"/);
  assert.match(agent.innerHTML,/data-message="m1"/);
  assert.match(agent.innerHTML,/href="#agent-itinerary"/);
  assert.match(agent.innerHTML,/href="#agent-cost"/);
});
