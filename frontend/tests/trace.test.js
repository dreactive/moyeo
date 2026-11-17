import test from 'node:test';
import assert from 'node:assert/strict';
import {loadTraces} from '../src/dev-trace.js';
test('trace token is sent only in a header and fixture rejection stays visible', async () => {
  globalThis.location = {search:'?mode=fixture'};
  await assert.rejects(loadTraces({room_id:'room-fixture',devToken:'bad'}),/403/);
  assert.equal((await loadTraces({room_id:'room-fixture',devToken:'fixture-dev'}))[0].run_id,'run-fixture');
  location.search='';
  let url,options;
  globalThis.fetch=async (path,init) => {url=path;options=init;return Response.json({runs:[]});};
  await loadTraces({room_id:'r',run_id:'run 1',devToken:'secret'});
  assert.equal(options.headers['X-Dev-Token'],'secret');
  assert.equal(url,'/api/dev/rooms/r/traces?run_id=run%201');
  assert.equal(options.credentials,'same-origin');
});
test('trace view connects comparative decisions tool results and applied state by call id', async () => {
  globalThis.location={search:'?mode=fixture'};
  const {renderTraces}=await import('../src/dev-trace.js');
  const runs=await loadTraces({room_id:'room-fixture',devToken:'fixture-dev'});
  let output='';
  globalThis.document={getElementById:() => ({set innerHTML(value){output=value;}})};
  renderTraces(runs);
  for (const value of ['decision','tool_call','tool_result','state_applied','call-fixture','selected_index','duration_ms','fake']) assert.ok(output.includes(value));
});
