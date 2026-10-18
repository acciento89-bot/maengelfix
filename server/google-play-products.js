import { readFileSync } from 'node:fs';
// Both the actually published Android 3 build and the future native client use these plans.
const currentProducts = new Map([
  ['maengelfix.private.monthly', {scope:'private',planCode:'private_pro'}],
  ['maengelfix.private.yearly', {scope:'private',planCode:'private_pro'}],
  ['maengelfix.starter.monthly', {scope:'organization',planCode:'management_starter'}],
  ['maengelfix.starter.yearly', {scope:'organization',planCode:'management_starter'}],
  ['maengelfix.pro.monthly', {scope:'organization',planCode:'management_pro'}],
  ['maengelfix.pro.yearly', {scope:'organization',planCode:'management_pro'}],
  ['maengelfix.business.monthly', {scope:'organization',planCode:'management_business'}],
  ['maengelfix.business.yearly', {scope:'organization',planCode:'management_business'}]
]);

export const legacyPlayProductAliases = new Map(Object.entries(JSON.parse(readFileSync(new URL('./google-play-legacy-products.json', import.meta.url), 'utf8'))));
export const googlePlayProducts = new Map(currentProducts);
for (const [legacy, current] of legacyPlayProductAliases) googlePlayProducts.set(legacy, currentProducts.get(current));
