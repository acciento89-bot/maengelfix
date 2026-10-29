"""One bounded listing-language inventory. No candidate or publishing operations."""
import copy
from datetime import datetime, timezone
import re
from candidate import EXPECTED
from business_policy import scope
from publisher import ok, definite_rejection, deletion_confirmed

def inspect_existing_locales(selector, catalog, transport, checkpoint=None, now=None, family='calculator9'):
    expected = scope(family); batch = 'all-nine' if family == 'calculator9' else 'all-twelve'
    report = {'schema':1,'operation':'inspect_existing_locales','ok':False,'status':'stopped',
        'inspectedAtUTC':(now or datetime.now(timezone.utc)).isoformat(),'apps':[]}
    if set(catalog) != set(expected) or selector not in set(expected) | {batch}:
        report['stoppedBecause'] = 'excluded_inventory_scope'; return report
    packages = sorted(expected) if selector == batch else [selector]
    def save():
        if checkpoint: checkpoint(copy.deepcopy(report))
    for package in packages:
        base = '/androidpublisher/v3/applications/'+package+'/edits'
        row = {'package':package,'status':'started','cleanup':{'attempted':False,'confirmed':False}}
        report['apps'].append(row); edit = None; failed = False; uncertain = False; creating = False; response = None
        try:
            save(); creating = True
            response = transport.request('POST',base,{})
            if not ok(response):
                uncertain = not definite_rejection(response)
                raise ValueError('edit_create_failed')
            value = response.data.get('id') if isinstance(response.data,dict) else None
            if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value) is None:
                uncertain = True; raise ValueError('edit_identity_unknown')
            edit = value; row['editId'] = edit; save()
            response = transport.request('GET',base+'/'+edit+'/listings')
            if not ok(response) or not isinstance(response.data,dict): raise ValueError('listings_read_failed')
            listings = response.data.get('listings',[])
            if not isinstance(listings,list) or len(listings)>100: raise ValueError('ambiguous_locale_ids')
            languages = []
            for listing in listings:
                language = listing.get('language') if isinstance(listing,dict) else None
                if not isinstance(language,str) or re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*',language) is None or len(language)>35 or language in languages:
                    raise ValueError('ambiguous_locale_ids')
                languages.append(language)
            row['localeIds'] = sorted(languages); row['status'] = 'ok'; save()
        except BaseException:
            failed = True
            if creating and edit is None and (response is None or ok(response)): uncertain = True
            row['status'] = 'inspection_failed'
        finally:
            if edit is not None:
                row['cleanup']['attempted'] = True
                try:
                    deleted = transport.request('DELETE',base+'/'+edit)
                    row['cleanup']['httpStatus'] = deleted.status
                    row['cleanup']['confirmed'] = deletion_confirmed(deleted)
                    if deleted.status == 200: row['cleanup']['emptyJsonAcknowledgement'] = deleted.data == {}
                except BaseException: row['cleanup']['confirmed'] = False
                if not row['cleanup']['confirmed']: uncertain = True; failed = True
        if failed:
            report['status'] = 'reconciliation_required' if uncertain else 'stopped'
            report['stoppedBecause'] = 'owned_edit_outcome_unknown' if uncertain else 'inventory_or_receipt_failed'
            break
        try: save()
        except BaseException:
            row['status'] = 'receipt_failed'; report['stoppedBecause'] = 'inventory_or_receipt_failed'; break
    else:
        report['ok'] = True; report['status'] = 'inspection_complete'
    return report
