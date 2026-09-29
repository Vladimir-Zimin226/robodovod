import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createCommercialSession} from '../../src/commercialScenariosModel.js';
const bundle=JSON.parse(await readFile(process.argv[2],'utf8'));
const session=createCommercialSession(bundle);
assert.ok(session.result);
for(const scenario of bundle.comparison.scenarios)assert.equal(typeof scenario.metrics.npv.value,'string');
