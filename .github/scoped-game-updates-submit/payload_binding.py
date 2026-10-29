import re
from candidate import require

def parse_installed_hash_proof(raw, package, apk_sha256):
    try:text=raw.decode('utf-8')
    except UnicodeError:require(False,'Invalid direct installed APK hash proof encoding')
    matches=re.findall(r'^([a-f0-9]{64})  (/data/app/.+/base\.apk)$',text,re.M)
    require(len(matches)==1 and matches[0][0]==apk_sha256 and '/'+package+'-' in matches[0][1], 'Direct actual installed APK hash/package path differs from current derived APK')
    pm=[line.removeprefix('package:') for line in text.splitlines()if line.startswith('package:')]
    require(not pm or pm==[matches[0][1]],'Optional pm path contradicts direct installed APK hash path')
    return {'apkSha256':matches[0][0],'path':matches[0][1],'pmPathIncluded':bool(pm)}
