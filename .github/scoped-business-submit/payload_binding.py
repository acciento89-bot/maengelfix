"""Verbatim bounded raw payload/hash validators from reviewed calculator pack helper."""
import re
from candidate import require,digest
from business_binary import binary_files

def verify_derived_payload(aab, apk):
    source=binary_files(aab);target=binary_files(apk);expected={};rows=[]
    for name,data in source.items():
        if name.startswith('base/dex/'):destination=name.removeprefix('base/dex/');role='DEX'
        elif name.startswith('base/lib/'):destination=name.removeprefix('base/');role='JNI'
        elif name.startswith('base/assets/'):destination=name.removeprefix('base/');role='originalAssets'
        elif name in ('BUNDLE-METADATA/com.android.tools.build.profiles/baseline.prof','BUNDLE-METADATA/com.android.tools.build.profiles/baseline.profm'):
            destination='assets/dexopt/'+name.rsplit('/',1)[1];role='baselineMetadataRelocation'
        else:continue
        require(destination not in expected,'Ambiguous AAB payload relocation');expected[destination]=data
        rows.append({'aabEntry':name,'apkEntry':destination,'sha256':digest(data),'role':role})
    actual={name:data for name,data in target.items()if name.startswith(('lib/','assets/'))or re.fullmatch(r'classes[0-9]*\.dex',name)}
    require(expected and set(actual)==set(expected)and all(actual[name]==data for name,data in expected.items()),'Actual APK DEX/JNI/original assets/baseline bytes differ from current signed AAB')
    return {'sourceAabSha256':digest(aab),'apkSha256':digest(apk),'matchingEntries':len(rows),'allSelectedRawEntriesByteExact':True,'entries':rows,
        'scope':'Actual DEX, JNI, original base assets and declared baseline-metadata relocations. Compiled manifest/resources/signature format differences are not claimed raw-identical.'}

def parse_installed_hash_proof(raw, package, apk_sha256):
    try:text=raw.decode('utf-8')
    except UnicodeError:require(False,'Invalid direct installed APK hash proof encoding')
    matches=re.findall(r'^([a-f0-9]{64})  (/data/app/.+/base\.apk)$',text,re.M)
    require(len(matches)==1 and matches[0][0]==apk_sha256 and '/'+package+'-' in matches[0][1], 'Direct actual installed APK hash/package path differs from current derived APK')
    pm=[line.removeprefix('package:') for line in text.splitlines()if line.startswith('package:')]
    require(not pm or pm==[matches[0][1]],'Optional pm path contradicts direct installed APK hash path')
    return {'apkSha256':matches[0][0],'path':matches[0][1],'pmPathIncluded':bool(pm)}
