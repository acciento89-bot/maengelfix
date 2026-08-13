from pathlib import Path
import re
p=Path('server/index.js');s=p.read_text()
# Separate in-app organization notifications from organization e-mails.
s=s.replace("async function notifyOrganization(organizationId, subject, text, caseId) {","async function emailOrganization(organizationId, subject, text, caseId) {")
s=re.sub(r"notifyOrganization\(([^,\n]+),(?=\s*[`\"'])",r"emailOrganization(\1,",s)
# Repair legacy SQL strings that embedded SQL single quotes inside JS single-quoted strings.
s=s.replace("'INSERT INTO case_events (id, case_id, user_id, event_type, note, visibility) VALUES ($1,$2,$3,$4,$5,'shared')'","`INSERT INTO case_events (id, case_id, user_id, event_type, note, visibility) VALUES ($1,$2,$3,$4,$5,'shared')`")
s=s.replace("'INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,$4,$5,'shared')'","`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,$4,$5,'shared')`")
s=s.replace("'INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,$4,$5,'internal')'","`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,$4,$5,'internal')`")
p.write_text(s)
print('startup notification and SQL syntax fixes applied')
