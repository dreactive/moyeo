import test from 'node:test';
import assert from 'node:assert/strict';
import * as ui from '../src/ui.js';
test('a pending control suppresses duplicate actions and becomes usable after failure', async () => {
  const button={disabled:false}; let reject;
  const first=ui.withPending?.(button,() => new Promise((a,b) => { reject=b; }));
  assert.equal(button.disabled,true);
  assert.equal(await ui.withPending?.(button,() => 2),undefined);
  reject(new Error('offline'));
  await assert.rejects(first,/offline/);
  assert.equal(button.disabled,false);
});
test('keyboard form submission shares the real button pending lock', async () => {
  const button={disabled:false}; const event={submitter:null,target:{querySelector:() => button}};
  const load=Promise.withResolvers(); let calls=0;
  const action=() => { calls++; return load.promise; };
  const first=ui.runFormAction?.(event,action),second=ui.runFormAction?.(event,action);
  assert.equal(calls,1); load.resolve(); await Promise.all([first,second]);
});
import {renderAgentBanner} from '../src/workspace-view.js';
test('an idle agent render cannot unlock a manual request in flight', async () => {
  const button={disabled:false,dataset:{}};
  globalThis.document={getElementById:id => id === 'replan' ? button : {set innerHTML(value){}}};
  const load=Promise.withResolvers();
  const pending=ui.withPending(button,() => load.promise);
  renderAgentBanner({questions:[],conflicts:[],agent_status:{label:'idle',state:'idle'}});
  assert.equal(button.disabled,true);
  load.resolve(); await pending;
});
