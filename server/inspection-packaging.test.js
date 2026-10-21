import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
test('production image supplies shared pure outbox model imported by server coordinator',async()=>{
 const docker=await readFile(new URL('../Dockerfile',import.meta.url),'utf8');const finalStage=docker.split('FROM node:22-alpine\n').at(-1);assert.ok(finalStage.includes('/src/client/src/inspection-outbox/core.js')&&finalStage.includes('./client/src/inspection-outbox/core.js'),'Final runtime image must include shared model at server relative import path');
});
