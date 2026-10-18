"""Match the published Android 3 catalog without replacing its complete workspace.
Copies only the owner's existing approved prices/regions; never purchases or edits originals.
"""
import json,os,urllib.request,urllib.error,urllib.parse,time
from pathlib import Path
package='com.kamilunavo.maengelfix'
root=Path(__file__).resolve().parents[1]
aliases=json.loads((root/'server/google-play-legacy-products.json').read_text())
assert len(aliases)==7 and all(a.startswith(package+'.') and b.startswith('maengelfix.') for a,b in aliases.items())
assert not any('business.yearly' in b for b in aliases.values())
mode=os.environ.get('CATALOG_MODE','audit');assert mode in ['audit','apply']
base='https://androidpublisher.googleapis.com/androidpublisher/v3/applications/'+package
headers={'Authorization':'Bearer '+os.environ['GOOGLE_ACCESS_TOKEN'],'Content-Type':'application/json'}
def call(url,body=None,optional=False):
 req=urllib.request.Request(url,headers=headers,data=None if body is None else json.dumps(body).encode())
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
 except urllib.error.HTTPError as e:
  if optional and e.code==404:return None
  d=json.loads(e.read()).get('error',{})
  raise RuntimeError('Google catalog operation failed: '+str(e.code)+' '+d.get('message','')) from None
conversion=call(base+'/pricing:convertRegionPrices',{'price':{'currencyCode':'EUR','units':'1'}})
version=conversion['regionVersion']['version'];assert version
rows=[]
for legacy,current in aliases.items():
 source=call(base+'/subscriptions/'+current)
 active=[p for p in source['basePlans'] if p['state']=='ACTIVE'];assert len(active)==1,current
 # Every commercial and regional setting is copied from the existing approved product.
 plan={k:v for k,v in active[0].items() if k!='state'}
 assert plan.get('autoRenewingBasePlanType',{}).get('billingPeriodDuration') in ['P1M','P1Y']
 price=next(x['price'] for x in plan['regionalConfigs'] if x['regionCode']=='DE')
 assert price['currencyCode']=='EUR' and float(price.get('units',0))+float(price.get('nanos',0))/1e9<=940
 body={'packageName':package,'productId':legacy,'basePlans':[plan],'listings':source['listings']}
 for key in ['taxAndComplianceSettings','restrictedPaymentCountries']:
  if key in source:body[key]=source[key]
 found=call(base+'/subscriptions/'+legacy,optional=True)
 if found:
  oldplans=[p for p in found['basePlans'] if p['basePlanId']==plan['basePlanId']];assert len(oldplans)==1,'Unexpected existing legacy base plan'
  # Never change existing prices, territories, plan periods or benefits on a retry.
  for key in ['regionalConfigs','autoRenewingBasePlanType','otherRegionsConfig']:
   assert oldplans[0].get(key)==plan.get(key), 'Existing legacy terms differ: '+legacy+' '+key
 elif mode=='apply':
  query=urllib.parse.urlencode({'productId':legacy,'regionsVersion.version':version})
  found=call(base+'/subscriptions?'+query,body)
 if mode=='apply':
  assert found
  target=next(p for p in found['basePlans'] if p['basePlanId']==plan['basePlanId'])
  if target['state']!='ACTIVE':
   found=call(base+'/subscriptions/'+legacy+'/basePlans/'+plan['basePlanId']+':activate',{})
  saved=call(base+'/subscriptions/'+legacy)
  target=next(p for p in saved['basePlans'] if p['basePlanId']==plan['basePlanId']);assert target['state']=='ACTIVE'
  assert next(x['price'] for x in target['regionalConfigs'] if x['regionCode']=='DE')==price
 rows.append({'legacyProduct':legacy,'samePlanAs':current,'germanPrice':price,'billingPeriod':plan['autoRenewingBasePlanType']['billingPeriodDuration'],'state':'ACTIVE' if mode=='apply' else ('EXISTS' if found else 'MISSING'),'regionCount':len(plan['regionalConfigs'])})
 print(legacy,rows[-1]['state'],flush=True)
Path('production-product-compatibility.json').write_text(json.dumps({'package':package,'mode':mode,'products':rows,'sourceProductsChanged':False,'businessAnnualOffered':False,'actualPurchasePerformed':False},indent=2)+'\n')
