"""Register the public CA using the documented IAM REST schema, without PEM rewriting."""
import base64,json,os,time,urllib.request,urllib.error
base='https://iam.googleapis.com/v1/'
parent='projects/1058001477767/locations/global/workloadIdentityPools/maengelfix-runtime'
name=parent+'/providers/prod-x509'
headers={'Authorization':'Bearer '+os.environ['GOOGLE_TOKEN'],'Content-Type':'application/json'}
def call(path,body=None):
 req=urllib.request.Request(base+path,headers=headers,data=None if body is None else json.dumps(body).encode())
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
 except urllib.error.HTTPError as e:
  error=json.loads(e.read()).get('error',{})
  if e.code==404 and body is None:return None
  raise RuntimeError('IAM public-provider configuration failed: '+str(e.code)+' '+error.get('message','')) from None
root=base64.b64decode(os.environ['ROOT_CERTIFICATE_B64']).decode().strip()
# Match Google's documented trust-store formatting: remove the final PEM newline.
assert '\r' not in root
assert root.startswith('-----BEGIN CERTIFICATE-----\n') and root.rstrip().endswith('-----END CERTIFICATE-----')
condition="assertion.subject.dn.cn == 'maengelfix-prod' && assertion.san.uri == 'spiffe://kamilunavo.com/maengelfix-prod'"
found=call(name)
if found:
 assert found['attributeCondition']==condition, 'Unexpected existing identity condition'
 assert found['x509']['trustStore']['trustAnchors'][0]['pemCertificate'].strip()==root.strip(), 'Unexpected existing CA'
else:
 op=call(parent+'/providers?workloadIdentityPoolProviderId=prod-x509',{
  'displayName':'MaengelFix production X509',
  'attributeMapping':{'google.subject':'assertion.subject.dn.cn'},
  'attributeCondition':condition,
  'x509':{'trustStore':{'trustAnchors':[{'pemCertificate':root}]}},
 })
 for _ in range(30):
  if op.get('done'):break
  time.sleep(2);op=call(op['name'])
 if op.get('error'):raise RuntimeError(op['error'].get('message','Provider operation failed'))
 assert op.get('done'), 'Provider operation did not complete'
 for _ in range(10):
  found=call(name)
  if found and found.get('state')=='ACTIVE':break
  time.sleep(2)
 assert found and found.get('state')=='ACTIVE'
print('Dedicated X509 provider verified with exact certificate CN and SPIFFE URI restriction.')
