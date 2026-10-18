import assert from 'node:assert/strict';
import {test} from 'node:test';
import {googlePlayProducts,legacyPlayProductAliases} from './google-play-products.js';

test('published Android 3 product identifiers retain the correct account scope',()=>{
 for(const [old,current] of legacyPlayProductAliases){
  const actual=googlePlayProducts.get(old);
  assert.ok(actual,old);assert.deepEqual(actual,googlePlayProducts.get(current));
  assert.equal(actual.scope,old.includes('.privatepro.')?'private':'organization');
 }
 assert.equal(legacyPlayProductAliases.size,7);
});
test('unknown products and unoffered legacy Business annual cannot grant access',()=>{
 assert.equal(googlePlayProducts.has('com.kamilunavo.maengelfix.managementbusiness.yearly'),false);
 assert.equal(googlePlayProducts.has('maengelfix.unknown.monthly'),false);
 assert.equal(googlePlayProducts.get('maengelfix.business.yearly').planCode,'management_business'); // preserve modern historical restore mapping
});
