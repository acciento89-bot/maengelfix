from pathlib import Path
import re
p=Path('server/index.js');s=p.read_text()
s=s.replace("async function notifyOrganization(organizationId, subject, text, caseId) {","async function emailOrganization(organizationId, subject, text, caseId) {")
# Calls whose second argument is a text literal belong to the e-mail helper; object payload calls remain In-App notifications.
s=re.sub(r"notifyOrganization\(([^,\n]+),(?=\s*[`\"'])",r"emailOrganization(\1,",s)
p.write_text(s)
print('duplicate notification helper fixed')
