from pathlib import Path
p=Path('server/index.js')
s=p.read_text()
needle='async function notifyOrganization('
positions=[]
i=0
while True:
    i=s.find(needle,i)
    if i<0: break
    positions.append(i); i+=len(needle)
if len(positions)>1:
    pos=positions[-1]
    s=s[:pos]+s[pos:].replace(needle,'async function notifyOrganizationLegacy(',1)
p.write_text(s)
print('notifyOrganization declarations:',len(positions),'-> cleaned')
