import test from 'node:test';
import assert from 'node:assert/strict';
import { limitOfflineUpload } from './inspection-outbox-routes.js';
function run(length){let next=false;const response={code:200,status(code){this.code=code;return this;},json(value){this.body=value;return this;}};limitOfflineUpload({headers:length===undefined?{}:{'content-length':length}},response,()=>{next=true;});return{next,response};}
test('bounded multipart framing prevents unbounded staging before any file is accepted',()=>{assert.equal(run('1024').next,true);assert.equal(run(String(22*1024*1024)).next,true);assert.equal(run(String(22*1024*1024+1)).response.code,413);});
test('missing malformed or contradictory framing is rejected before staging',()=>{for(const length of [undefined,'-1','0','1.5','123abc','1e9']){const result=run(length);assert.equal(result.next,false);assert.equal(result.response.code,411);}});
