"""Frozen exact original 9351 payloads and8642 named source voices, one member at a time."""
import re
from candidate import require,digest
from stream_zip import mapping,FileRef,PINS

def verify_derived_payload(aab,apk):
 from business_policy import registry
 require(isinstance(aab,FileRef)and aab.role=='aab'and isinstance(apk,FileRef)and apk.role=='apk','Only exact frozen NavoKids AAB/APK file refs')
 app=registry();source=mapping(aab);target=mapping(apk);expected=app['payloadMap']['originalMappedPayload'];require(len(expected)==9351,'Original payload map count differs');count=0
 for name,sha in expected.items():
  candidates=[n for n in ['base/dex/'+name,'base/root/'+name,'base/'+name]if n in source]
  require(len(candidates)==1 and name in target,'Missing/ambiguous exact original payload relocation');require(source.entry_hash(candidates[0])==target.entry_hash(name)==sha,'Original AAB/APK raw payload differs');count+=1
 extras=app['payloadMap']['generatedBaselineMetadataExtras']
 for name,sha in extras.items():require(name in target and target.entry_hash(name)==sha,'Generated baseline metadata differs')
 voices=app['voiceMap'];require(len(voices)==8642 and len({v['aabEntry']for v in voices})==8642,'Named source voice count/aliases differ')
 for v in voices:require(v['aabEntry']in source and v['apkEntry']in target and source.entry_hash(v['aabEntry'])==target.entry_hash(v['apkEntry'])==v['sha256'],'Named original source voice differs')
 source.close();target.close();return {'sourceAabSha256':aab.sha256,'apkSha256':apk.sha256,'matchingEntries':count,'exactNamedVoiceEntries':len(voices),'allSelectedRawEntriesByteExact':True,'fullBinarySHAsBeforeParsing':True,'streamChunkBytes':1024*1024,'scope':'9351 exact frozen mapped raw entries including res/raw/voice, fonts,root metadata;8642 named source voice clips. Compiled XML/resources table and signatures differ by format and are not relabelled raw-equal. Both complete binaries are separately SHA-pinned.'}

def parse_installed_hash_proof(raw,package,apk_sha256):
 try:text=raw.decode('utf-8')
 except UnicodeError:require(False,'Invalid direct installed APK hash proof encoding')
 matches=re.findall(r'^([a-f0-9]{64})  (/data/app/.+/base\.apk)$',text,re.M)
 require(len(matches)==1 and matches[0][0]==apk_sha256 and '/'+package+'-'in matches[0][1],'Direct actual installed APK hash/package path differs')
 pm=[line.removeprefix('package:')for line in text.splitlines()if line.startswith('package:')];require(not pm or pm==[matches[0][1]],'Optional pm path contradicts direct installed hash');return {'apkSha256':matches[0][0],'path':matches[0][1]}
