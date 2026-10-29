"""Bounded raw DEX/JNI/base-assets and every install-time asset mapping."""
import re
from candidate import require,digest
from game_binary import binary_files as zip_files

def verify_derived_payload(aab,apk,app):
    source=zip_files(aab);actual_files=zip_files(apk);expected={};origins={}
    for name,data in source.items():
        target=None
        if name.startswith('base/dex/')and name.endswith('.dex'):target=name[len('base/dex/'):]
        elif name.startswith(('base/lib/','base/assets/')):target=name[len('base/'):]
        elif name.startswith('assetPackInstallTime/assets/'):target='assets/'+name[len('assetPackInstallTime/assets/'):]
        elif re.match(r'[^/]+/assets/',name):require(False,'Unaccounted asset module')
        if target is not None:
            require(target not in expected,'AAB modules collide at APK target');expected[target]=digest(data);origins[target]=name
    actual={n:digest(data)for n,data in actual_files.items()if re.fullmatch(r'classes[0-9]*\.dex',n)or n.startswith(('lib/','assets/'))}
    extras=set(actual)-set(expected);known=app['allowedGeneratedBaselineExtras']
    require(expected and extras==set(known)and set(expected)<=set(actual)and all(actual[n]==h for n,h in expected.items())and all(actual[n]==h for n,h in known.items()),'Lost/changed/extra base DEX/JNI/assets or install-time pack/baseline metadata')
    install=sum(n.startswith('assetPackInstallTime/assets/')for n in origins.values())
    if app['engine']=='Godot':require(install>0 and install==app['sourceTopology']['installTimeAssetFiles'],'All install-time pack files are mandatory; base-only pairing forbidden')
    else:require(install==0,'Unexpected Unity install-time module')
    return {'sourceAabSha256':digest(aab),'apkSha256':digest(apk),'matchingMappedEntries':len(expected),'installTimeAssets':install,'allSelectedRawBytesExact':True,'compiledResourcesAndManifestRawEqualityClaimed':False}
