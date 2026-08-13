from pathlib import Path
root=Path('.')
app_p=root/'client/src/App.jsx'; server_p=root/'server/index.js'
app=app_p.read_text(); server=server_p.read_text()
app=app.replace("<AccountSecurityView user={user} onUserChanged={setUser} onSignedOut={onSignedOut} />","<AccountSecurityView user={user} onUserChanged={setUser} onSignedOut={onLogout} />")
old="const data = await api('/api/cases', { method: 'POST', body: JSON.stringify(form) });\n      onCreated(data.case);"
new="let data = await api('/api/cases', { method: 'POST', body: JSON.stringify(form) });\n      if(form.purchaseOn||form.purchasePrice||form.warrantyUntil||form.desiredResolution){const patched=await api(`/api/cases/${data.case.id}`,{method:'PATCH',body:JSON.stringify({purchaseOn:form.purchaseOn||null,purchasePrice:form.purchasePrice||null,warrantyUntil:form.warrantyUntil||null,desiredResolution:form.desiredResolution||null})});data={...data,case:patched.case};}\n      onCreated(data.case);"
app=app.replace(old,new)
# Private billing needs customer id to show portal button.
server=server.replace("SELECT plan_code,subscription_status,subscription_provider,subscription_current_period_end FROM users WHERE id=$1","SELECT plan_code,subscription_status,subscription_provider,subscription_customer_id,subscription_id,subscription_current_period_end FROM users WHERE id=$1")
# Search should include the user's digitally submitted cases even after they were sent to a management organization.
server=server.replace("WHERE ((c.organization_id IS NULL AND c.user_id=$1) OR ($2::text IS NOT NULL AND c.organization_id=$2)) AND (($7=true", "WHERE (c.user_id=$1 OR ($2::text IS NOT NULL AND c.organization_id=$2)) AND (($7=true")
app_p.write_text(app);server_p.write_text(server)
print('v0.15 completion fixes applied')
