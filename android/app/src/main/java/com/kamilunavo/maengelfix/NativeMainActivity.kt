package com.kamilunavo.maengelfix

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AddAPhoto
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.DeleteForever
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaengelFixNativeApp(this) }
    }
}

private val MfPrimary = Color(0xFF2457D6)
private val MfAccent = Color(0xFFE5A31B)
private val MfInk = Color(0xFF18212B)
private val MfBackground = Color(0xFFF3F5F7)
private val MfSuccess = Color(0xFF18845D)
private val MfColors = lightColorScheme(
    primary = MfPrimary, onPrimary = Color.White, secondary = MfAccent, onSecondary = MfInk,
    background = MfBackground, onBackground = MfInk, surface = Color.White, onSurface = MfInk,
    surfaceVariant = Color(0xFFEDF1F6), onSurfaceVariant = Color(0xFF667085),
    outline = Color(0xFFD9E0E8), error = Color(0xFFD04444),
)
private enum class AppTab { DASHBOARD, CASES, CREATE, PROFILE }

@Composable
private fun MaengelFixNativeApp(activity: MainActivity) {
    val api = remember { NativeApiClient() }
    val scope = rememberCoroutineScope()
    var user by remember { mutableStateOf<MfUser?>(null) }
    var cases by remember { mutableStateOf<List<DefectCase>>(emptyList()) }
    var management by remember { mutableStateOf<ManagementOverview?>(null) }
    var loading by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf<String?>(null) }
    var billingMessage by remember { mutableStateOf<String?>(null) }
    var billingVersion by remember { mutableStateOf(0) }
    var tab by remember { mutableStateOf(AppTab.DASHBOARD) }
    var selectedCase by remember { mutableStateOf<String?>(null) }
    var showBilling by remember { mutableStateOf(false) }

    suspend fun refresh() {
        val current = api.me()
        user = current
        cases = api.cases()
        management = if (current.isManagement) runCatching { api.managementOverview() }.getOrNull() else null
    }

    val billing = remember(activity) {
        BillingManager(
            activity,
            { activity.runOnUiThread { billingVersion++ } },
            { activity.runOnUiThread { showBilling = false; scope.launch { runCatching { refresh() } } } },
            { value -> activity.runOnUiThread { billingMessage = value } },
        )
    }
    DisposableEffect(Unit) { onDispose { billing.close() } }
    LaunchedEffect(Unit) {
        try { refresh() }
        catch (error: NativeApiException) { if (error.statusCode != 401) message = error.message }
        catch (error: Exception) { message = error.message }
        loading = false
    }
    BackHandler(enabled = user != null) {
        when {
            showBilling -> showBilling = false
            selectedCase != null -> selectedCase = null
            tab != AppTab.DASHBOARD -> tab = AppTab.DASHBOARD
            else -> activity.moveTaskToBack(true)
        }
    }

    MaterialTheme(
        colorScheme = MfColors,
        shapes = MaterialTheme.shapes.copy(small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(14.dp), large = RoundedCornerShape(22.dp)),
    ) {
        when {
            loading -> LoadingScreen()
            user == null -> AuthScreen(
                message,
                onForgot = { email -> scope.launch { message = runCatching { api.forgot(email) }.getOrElse { it.message ?: "Anfrage fehlgeschlagen." } } },
                onLogin = { email, password -> scope.launch { loading = true; message = null; runCatching { api.login(email, password); refresh() }.onFailure { message = it.message }; loading = false } },
                onRegister = { name, email, password, type, org -> scope.launch { loading = true; message = null; runCatching { api.register(name, email, password, type, org); refresh() }.onFailure { message = it.message }; loading = false } },
            )
            showBilling -> PlayBillingSheet(billing, billingVersion) { showBilling = false }
            selectedCase != null -> CaseDetailScreen(activity, api, selectedCase!!, { selectedCase = null }) { scope.launch { runCatching { cases = api.cases() } } }
            else -> Scaffold(containerColor = MfBackground, bottomBar = { BottomNavigation(tab) { tab = it } }) { padding ->
                Box(Modifier.fillMaxSize().padding(padding)) {
                    when (tab) {
                        AppTab.DASHBOARD -> DashboardScreen(user!!, cases, management, message, { selectedCase = it }) { scope.launch { runCatching { refresh() }.onFailure { message = it.message } } }
                        AppTab.CASES -> CasesScreen(cases) { selectedCase = it }
                        AppTab.CREATE -> CreateCaseScreen(activity, api, user!!.isManagement) { created -> cases = listOf(created) + cases.filterNot { it.id == created.id }; tab = AppTab.CASES; selectedCase = created.id }
                        AppTab.PROFILE -> ProfileScreen(activity, user!!, billingMessage, { user = it }, { showBilling = true }, { scope.launch { runCatching { api.resendVerification(); message = "Bestätigungs-E-Mail wurde versendet." }.onFailure { message = it.message } } }, { scope.launch { api.logout(); user = null; cases = emptyList() } }, { password -> scope.launch { runCatching { api.deleteAccount(password); user = null; cases = emptyList() }.onFailure { message = it.message } } })
                    }
                }
            }
        }
    }
}

@Composable
private fun LoadingScreen() = Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) { MfLogo(); CircularProgressIndicator(Modifier.padding(top = 24.dp)); Text("MängelFix wird geladen …", modifier = Modifier.padding(top = 12.dp)) }
}

@Composable
private fun MfLogo(compact: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Surface(color = MfInk, shape = RoundedCornerShape(if (compact) 8.dp else 10.dp)) { Icon(Icons.Default.Description, null, tint = MfAccent, modifier = Modifier.padding(if (compact) 8.dp else 11.dp).size(if (compact) 22.dp else 27.dp)) }
        Column(Modifier.padding(start = 10.dp)) {
            Text("MängelFix", style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
            if (!compact) Text("DOKUMENTIEREN · ORGANISIEREN · NACHWEISEN", fontSize = 8.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.6.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun AuthScreen(message: String?, onForgot: (String) -> Unit, onLogin: (String, String) -> Unit, onRegister: (String, String, String, String, String?) -> Unit) {
    var register by remember { mutableStateOf(false) }
    var management by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }; var org by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize().statusBarsPadding(), contentPadding = PaddingValues(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            MfLogo()
            Text(if (!register) "Willkommen zurück" else if (management) "MängelFix Verwaltung starten" else "MängelFix Privat starten", fontSize = 30.sp, lineHeight = 36.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 24.dp))
            Text(if (!register) "Deine Vorgänge sind mit demselben Konto wie im Web und auf iOS verfügbar." else "Dein digitaler Mängelordner – klar, sicher und nachvollziehbar.", textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp))
        }
        item { ToggleChoice(!register, "Anmelden", { register = false }, register, "Registrieren", { register = true }) }
        if (register) item {
            Text("Wie möchtest du MängelFix nutzen?", fontWeight = FontWeight.Bold, modifier = Modifier.fillMaxWidth())
            ToggleChoice(!management, "Privat", { management = false }, management, "Hausverwaltung", { management = true })
            Text(if (management) "14 Tage alle Verwaltungsfunktionen kostenlos testen." else "Privat Free bleibt dauerhaft kostenlos.", style = MaterialTheme.typography.bodySmall, color = MfPrimary, modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
        }
        item {
            if (register) MfField(name, { name = it }, "Dein Name")
            if (register && management) MfField(org, { org = it }, "Name der Hausverwaltung")
            MfField(email, { email = it }, "E-Mail")
            MfField(password, { password = it }, "Passwort", password = true)
            message?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) }
        }
        item {
            PrimaryButton(if (!register) "Anmelden" else if (management) "14 Tage kostenlos testen" else "Privatkonto erstellen", email.contains("@") && password.length >= 8 && (!register || name.isNotBlank()) && (!management || org.isNotBlank())) {
                if (register) onRegister(name, email, password, if (management) "management" else "private", org.takeIf { management }) else onLogin(email, password)
            }
            if (!register) TextButton(onClick = { if (email.contains("@")) onForgot(email) }) { Text("Passwort vergessen?") }
        }
        item { Text("MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.", style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
private fun ToggleChoice(firstSelected: Boolean, first: String, firstClick: () -> Unit, secondSelected: Boolean, second: String, secondClick: () -> Unit) = Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
    ChoiceButton(first, firstSelected, firstClick, Modifier.weight(1f)); ChoiceButton(second, secondSelected, secondClick, Modifier.weight(1f))
}

@Composable
private fun ChoiceButton(label: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Surface(onClick = onClick, modifier = modifier.height(48.dp), shape = RoundedCornerShape(12.dp), color = if (selected) MfPrimary else Color.White, border = BorderStroke(1.dp, if (selected) MfPrimary else MaterialTheme.colorScheme.outline)) {
        Box(contentAlignment = Alignment.Center) { Text(label, fontWeight = FontWeight.Bold, color = if (selected) Color.White else MfInk, textAlign = TextAlign.Center) }
    }
}

@Composable
private fun MfField(value: String, onValue: (String) -> Unit, label: String, password: Boolean = false, minLines: Int = 1) {
    OutlinedTextField(value, onValue, label = { Text(label) }, modifier = Modifier.fillMaxWidth().padding(top = 10.dp), singleLine = minLines == 1, minLines = minLines, shape = RoundedCornerShape(13.dp), visualTransformation = if (password) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None)
}

@Composable
private fun BottomNavigation(selected: AppTab, onSelect: (AppTab) -> Unit) = Surface(color = Color.White, shadowElevation = 12.dp) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 4.dp), horizontalArrangement = Arrangement.SpaceAround) {
        BottomItem(AppTab.DASHBOARD, selected, Icons.Default.Dashboard, "Übersicht", onSelect)
        BottomItem(AppTab.CASES, selected, Icons.Default.Assignment, "Mängel", onSelect)
        BottomItem(AppTab.CREATE, selected, Icons.Default.Add, "Neu", onSelect, true)
        BottomItem(AppTab.PROFILE, selected, Icons.Default.AccountCircle, "Profil", onSelect)
    }
}

@Composable
private fun RowScope.BottomItem(tab: AppTab, selected: AppTab, icon: ImageVector, label: String, onSelect: (AppTab) -> Unit, emphasized: Boolean = false) {
    val active = tab == selected
    Surface(onClick = { onSelect(tab) }, modifier = Modifier.weight(1f), color = Color.Transparent) {
        Column(Modifier.padding(vertical = 7.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(color = if (emphasized) MfPrimary else if (active) MfPrimary.copy(alpha = 0.11f) else Color.Transparent, shape = CircleShape) { Icon(icon, label, tint = if (emphasized) Color.White else if (active) MfPrimary else MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(if (emphasized) 9.dp else 5.dp).size(if (emphasized) 25.dp else 23.dp)) }
            Text(label, fontSize = 11.sp, fontWeight = if (active) FontWeight.Bold else FontWeight.Medium, color = if (active) MfPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun DashboardScreen(user: MfUser, cases: List<DefectCase>, management: ManagementOverview?, message: String?, onCase: (String) -> Unit, onRefresh: () -> Unit) {
    val open = cases.count { it.status != "resolved" && it.archivedAt == null }
    val resolved = cases.count { it.status == "resolved" }
    val deadlines = cases.count { it.deadlineOn.isNotBlank() && it.status != "resolved" }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp, 20.dp, 16.dp, 28.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { Text(if (user.isManagement) "Verwaltung" else "Übersicht", fontSize = 32.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f)); IconButton(onClick = onRefresh) { Icon(Icons.Default.Refresh, "Aktualisieren", tint = MfPrimary) } } }
        item { MfCard { Row(verticalAlignment = Alignment.Top) { MfLogo(true); Column(Modifier.weight(1f).padding(start = 14.dp)) { Text(if (user.isManagement) management?.organizationName ?: "MängelFix Verwaltung" else "Hallo, ${user.name}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); Text(if (user.isManagement) "Hier siehst du den aktuellen Stand deiner Verwaltung." else "Dein MängelFix Konto ist bereit.", color = MaterialTheme.colorScheme.onSurfaceVariant) }; PlanBadge(user.planLabel) } } }
        message?.let { item { MfCard { Text(it, color = MaterialTheme.colorScheme.error) } } }
        if (user.isManagement && management != null) {
            item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) { MetricCard("Objekte", management.metrics.properties, Icons.Default.Apartment, Modifier.weight(1f)); MetricCard("Einheiten", management.metrics.units, Icons.Default.FolderOpen, Modifier.weight(1f)) } }
            item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) { MetricCard("Offen", management.metrics.open, Icons.Default.Assignment, Modifier.weight(1f)); MetricCard("Überfällig", management.metrics.overdue, Icons.Default.CalendarMonth, Modifier.weight(1f)) } }
            item { MfCard { Text("Team", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); if (management.members.isEmpty()) EmptyText("Noch keine Teamdaten vorhanden.") else management.members.take(5).forEach { member -> HorizontalDivider(Modifier.padding(vertical = 9.dp)); Row { Text(member.name, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f)); Text("${member.openCases} offen", color = MaterialTheme.colorScheme.onSurfaceVariant) } } } }
        } else item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) { MetricCard("Offen", open, Icons.Default.Assignment, Modifier.weight(1f)); MetricCard("Erledigt", resolved, Icons.Default.CheckCircle, Modifier.weight(1f)); MetricCard("Fristen", deadlines, Icons.Default.CalendarMonth, Modifier.weight(1f)) } }
        item { MfCard { Text("Zuletzt aktualisiert", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); if (cases.isEmpty()) EmptyText("Noch keine Vorgänge. Lege deinen ersten Mangel über „Neu“ an.") else cases.take(5).forEach { CaseLine(it, onCase) } } }
    }
}

@Composable
private fun MetricCard(label: String, value: Int, icon: ImageVector, modifier: Modifier) = MfCard(modifier) { Icon(icon, null, tint = MfPrimary); Text("$value", fontSize = 28.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 7.dp)); Text(label, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
@Composable private fun PlanBadge(label: String) { Text(label, fontSize = 10.sp, fontWeight = FontWeight.Bold, color = MfPrimary, textAlign = TextAlign.End, modifier = Modifier.padding(start = 6.dp, top = 5.dp)) }

@Composable
private fun CasesScreen(cases: List<DefectCase>, onCase: (String) -> Unit) {
    var search by remember { mutableStateOf("") }
    val filtered = cases.filter { search.isBlank() || it.title.contains(search, true) || it.category.contains(search, true) || it.propertyLabel.contains(search, true) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp, 20.dp, 16.dp, 28.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
        item { Text("Mängel", fontSize = 32.sp, fontWeight = FontWeight.Bold); OutlinedTextField(search, { search = it }, leadingIcon = { Icon(Icons.Default.Search, null) }, label = { Text("Titel, Objekt oder Kategorie") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 12.dp), shape = RoundedCornerShape(14.dp)) }
        if (filtered.isEmpty()) item { EmptyState(Icons.Default.Assignment, if (search.isBlank()) "Noch keine Mängel" else "Keine Treffer", if (search.isBlank()) "Lege deinen ersten Mangel über den Tab „Neu“ an." else "Versuche einen anderen Suchbegriff.") }
        items(filtered, key = { it.id }) { CaseCard(it, onCase) }
    }
}

@Composable
private fun CaseCard(item: DefectCase, onCase: (String) -> Unit) {
    Surface(onClick = { onCase(item.id) }, color = Color.White, shape = RoundedCornerShape(14.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.Top) {
            Surface(color = if (item.status == "resolved") MfSuccess else MfAccent, shape = RoundedCornerShape(3.dp), modifier = Modifier.width(5.dp).height(62.dp)) {}
            Column(Modifier.weight(1f).padding(start = 12.dp)) { Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold); Text(listOf(item.statusLabel, item.category).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp)); if (item.propertyLabel.isNotBlank()) Text(item.propertyLabel, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp)) }
            if (item.attachmentCount > 0) Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.AttachFile, null, modifier = Modifier.size(16.dp)); Text("${item.attachmentCount}", fontSize = 12.sp) }
        }
    }
}

@Composable
private fun CaseLine(item: DefectCase, onCase: (String) -> Unit) = Surface(onClick = { onCase(item.id) }, color = Color.Transparent) {
    Row(Modifier.fillMaxWidth().padding(vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
        Surface(color = if (item.status == "resolved") MfSuccess else MfAccent, shape = CircleShape, modifier = Modifier.size(8.dp)) {}
        Column(Modifier.weight(1f).padding(start = 12.dp)) { Text(item.title, fontWeight = FontWeight.SemiBold); Text(item.statusLabel, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (item.attachmentCount > 0) Row { Icon(Icons.Default.AttachFile, null, modifier = Modifier.size(15.dp)); Text("${item.attachmentCount}", fontSize = 12.sp) }
    }
}

@Composable
private fun CreateCaseScreen(activity: MainActivity, api: NativeApiClient, management: Boolean, onCreated: (DefectCase) -> Unit) {
    val scope = rememberCoroutineScope()
    var title by remember { mutableStateOf("") }; var description by remember { mutableStateOf("") }
    var context by remember { mutableStateOf("housing") }; var category by remember { mutableStateOf("Feuchtigkeit / Schimmel") }
    var property by remember { mutableStateOf("") }; var location by remember { mutableStateOf("") }
    var recipient by remember { mutableStateOf("") }; var recipientEmail by remember { mutableStateOf("") }; var recipientAddress by remember { mutableStateOf("") }
    var discovered by remember { mutableStateOf("") }; var deadlineEnabled by remember { mutableStateOf(false) }; var deadline by remember { mutableStateOf("") }
    var photos by remember { mutableStateOf<List<UploadFile>>(emptyList()) }; var busy by remember { mutableStateOf(false) }; var error by remember { mutableStateOf<String?>(null) }
    val areas = listOf("housing" to "Wohnen / Immobilie", "delivery" to "Lieferung", "product" to "Produkt", "service" to "Dienstleistung", "vehicle" to "Fahrzeug", "travel" to "Reise", "other" to "Sonstiges")
    val categories = mapOf(
        "housing" to listOf("Feuchtigkeit / Schimmel", "Heizung / Warmwasser", "Sanitär", "Elektro", "Fenster / Türen", "Boden / Wand", "Lärm", "Außenbereich", "Sonstiges"),
        "delivery" to listOf("Transportschaden", "Verpackung beschädigt", "Produkt beschädigt", "Falsche Lieferung", "Fehlteil / unvollständig", "Sonstiges"),
        "product" to listOf("Beschädigung", "Funktionsmangel", "Qualitätsmangel", "Fehlteil / unvollständig", "Materialfehler", "Sonstiges"),
        "service" to listOf("Ausführung mangelhaft", "Leistung unvollständig", "Beschädigung verursacht", "Termin / Verzögerung", "Sonstiges"),
        "vehicle" to listOf("Motor / Antrieb", "Bremsen", "Fahrwerk / Lenkung", "Elektrik / Elektronik", "Karosserie / Lack", "Klima / Heizung", "Sonstiges"),
        "travel" to listOf("Unterkunft / Zimmer", "Sauberkeit / Hygiene", "Ausstattung defekt / fehlt", "Lärm", "Transport / Transfer", "Sonstiges"),
        "other" to listOf("Beschädigung", "Funktionsmangel", "Qualitätsmangel", "Sonstiges"),
    )
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris -> photos = uris.take(5).mapNotNull { activity.readUpload(it) } }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp, 20.dp, 16.dp, 110.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Text(if (management) "Neuer Vorgang" else "Neuer Mangel", fontSize = 32.sp, fontWeight = FontWeight.Bold) }
        item { MfCard { SectionTitle("Mangel", Icons.Default.Assignment); MfField(title, { title = it }, "Titel"); Text("Bereich", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 14.dp)); ChipGrid(areas, context) { value -> context = value; category = categories[value]?.first() ?: "Sonstiges" }; Text("Kategorie", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 14.dp)); ChipGrid(categories[context].orEmpty().map { it to it }, category) { category = it }; MfField(discovered, { discovered = it }, "Festgestellt am · JJJJ-MM-TT") } }
        item { MfCard { SectionTitle("Beschreibung", Icons.Default.Description); MfField(description, { description = it }, "Was ist passiert?", minLines = 5) } }
        item { MfCard { SectionTitle("Fotos", Icons.Default.AddAPhoto); OutlinedButton(onClick = { picker.launch("image/*") }, modifier = Modifier.fillMaxWidth().height(54.dp).padding(top = 8.dp)) { Icon(Icons.Default.AddAPhoto, null); Spacer(Modifier.width(8.dp)); Text("Mediathek öffnen (${photos.size}/5)", fontWeight = FontWeight.Bold) }; if (photos.isNotEmpty()) Text(photos.joinToString(" · ") { it.fileName }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp)) } }
        item { MfCard { SectionTitle("Ort / Bezug", Icons.Default.Apartment); MfField(property, { property = it }, "Objekt / Adresse (optional)"); MfField(location, { location = it }, "Raum / Ort (optional)") } }
        if (!management) item { MfCard { SectionTitle("Empfänger", Icons.Default.Send); MfField(recipient, { recipient = it }, "Name / Firma (optional)"); MfField(recipientEmail, { recipientEmail = it }, "E-Mail (optional)"); MfField(recipientAddress, { recipientAddress = it }, "Anschrift (optional)", minLines = 2) } }
        item { MfCard { Row(verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { SectionTitle("Frist", Icons.Default.CalendarMonth); Text("Rückmeldefrist für diesen Vorgang", color = MaterialTheme.colorScheme.onSurfaceVariant) }; Switch(deadlineEnabled, { deadlineEnabled = it }) }; if (deadlineEnabled) MfField(deadline, { deadline = it }, "Frist bis · JJJJ-MM-TT") } }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item {
            PrimaryButton(if (busy) "Wird angelegt …" else "Mangel anlegen", !busy && title.isNotBlank() && description.isNotBlank()) {
                scope.launch {
                    busy = true; error = null
                    runCatching {
                        val created = api.createCase(mapOf("title" to title.trim(), "description" to description.trim(), "caseContext" to context, "category" to category, "propertyLabel" to property, "locationLabel" to location, "discoveredOn" to discovered, "recipientName" to recipient.takeIf { !management }, "recipientEmail" to recipientEmail.takeIf { !management }, "recipientAddress" to recipientAddress.takeIf { !management }, "deadlineOn" to deadline.takeIf { deadlineEnabled }))
                        if (photos.isNotEmpty()) api.uploadImages(created.id, photos)
                        onCreated(created)
                    }.onFailure { error = it.message }
                    busy = false
                }
            }
        }
    }
}

@Composable
private fun ChipGrid(values: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit) = Column(verticalArrangement = Arrangement.spacedBy(7.dp), modifier = Modifier.padding(top = 7.dp)) {
    values.chunked(2).forEach { row -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) { row.forEach { item -> ChoiceButton(item.second, item.first == selected, { onSelect(item.first) }, Modifier.weight(1f)) }; if (row.size == 1) Spacer(Modifier.weight(1f)) } }
}

@Composable
private fun CaseDetailScreen(activity: MainActivity, api: NativeApiClient, id: String, onBack: () -> Unit, onChanged: () -> Unit) {
    val scope = rememberCoroutineScope()
    var detail by remember { mutableStateOf<CaseDetail?>(null) }; var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf("") }; var status by remember { mutableStateOf("") }; var busy by remember { mutableStateOf(false) }
    suspend fun load() { runCatching { detail = api.caseDetail(id); status = detail!!.caseItem.status }.onFailure { error = it.message } }
    LaunchedEffect(id) { load() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris -> scope.launch { busy = true; runCatching { api.uploadImages(id, uris.take(5).mapNotNull { activity.readUpload(it) }); load(); onChanged() }.onFailure { error = it.message }; busy = false } }
    LazyColumn(Modifier.fillMaxSize().statusBarsPadding(), contentPadding = PaddingValues(16.dp, 8.dp, 16.dp, 30.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Zurück") }; Text("Vorgang", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f)); IconButton(onClick = { activity.downloadPdf(api, id) }) { Icon(Icons.Default.PictureAsPdf, "PDF") } } }
        if (detail == null && error == null) item { Box(Modifier.fillMaxWidth().height(240.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
        error?.let { item { MfCard { Text(it, color = MaterialTheme.colorScheme.error) } } }
        detail?.let { data ->
            item { MfCard { Row { StatusBadge(data.caseItem.statusLabel, data.caseItem.status == "resolved"); Spacer(Modifier.weight(1f)); Text(data.caseItem.category, color = MaterialTheme.colorScheme.onSurfaceVariant) }; Text(data.caseItem.title, fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 14.dp)); Text(data.caseItem.description, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp)); Fact(Icons.Default.Apartment, listOf(data.caseItem.propertyLabel, data.caseItem.locationLabel).filter { it.isNotBlank() }.joinToString(" · ")); Fact(Icons.Default.CalendarMonth, listOf(data.caseItem.discoveredOn.takeIf { it.isNotBlank() }?.let { "Festgestellt: $it" }, data.caseItem.deadlineOn.takeIf { it.isNotBlank() }?.let { "Frist: $it" }).filterNotNull().joinToString(" · ")); if (data.caseItem.recipientName.isNotBlank()) Fact(Icons.Default.Send, data.caseItem.recipientName) } }
            item { MfCard { SectionTitle("Status", Icons.Default.Edit); ChipGrid(listOf("draft" to "Entwurf", "sent" to "Versendet", "reply" to "Rückmeldung", "reviewing" to "In Prüfung", "in_progress" to "In Bearbeitung", "resolved" to "Erledigt"), status) { next -> status = next; scope.launch { busy = true; runCatching { api.updateCase(id, mapOf("status" to next)); load(); onChanged() }.onFailure { error = it.message }; busy = false } } } }
            item { MfCard { Row(verticalAlignment = Alignment.CenterVertically) { SectionTitle("Nachweise", Icons.Default.AttachFile); Spacer(Modifier.weight(1f)); if (busy) CircularProgressIndicator(Modifier.size(20.dp)) }; OutlinedButton(onClick = { picker.launch("image/*") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) { Icon(Icons.Default.AddAPhoto, null); Spacer(Modifier.width(8.dp)); Text("Fotos hinzufügen") }; if (data.attachments.isEmpty()) EmptyText("Noch keine Fotos oder Dokumente vorhanden.") else data.attachments.forEach { attachment -> Surface(onClick = { activity.openUrl(api.attachmentUrl(attachment.id)) }, color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(10.dp), modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) { Row(Modifier.padding(12.dp)) { Icon(if (attachment.mimeType == "application/pdf") Icons.Default.PictureAsPdf else Icons.Default.AddAPhoto, null); Text(attachment.originalName, modifier = Modifier.padding(start = 9.dp)) } } } } }
            if (data.messages.isNotEmpty() || data.caseItem.submittedByTenant) item { MfCard { SectionTitle("Nachrichten", Icons.Default.Send); data.messages.forEach { msg -> Text(msg.actorName.ifBlank { "Nachricht" }, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 10.dp)); Text(msg.message); Text(msg.createdAt, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }; MfField(message, { message = it }, "Nachricht schreiben", minLines = 3); PrimaryButton("Nachricht senden", message.isNotBlank()) { scope.launch { runCatching { api.sendMessage(id, message); message = ""; load() }.onFailure { error = it.message } } } } }
            item { MfCard { SectionTitle("Verlauf", Icons.Default.Assignment); if (data.events.isEmpty()) EmptyText("Noch keine Verlaufseinträge.") else data.events.forEach { event -> HorizontalDivider(Modifier.padding(vertical = 9.dp)); Text(event.note.ifBlank { "Status aktualisiert" }, fontWeight = FontWeight.SemiBold); Text(listOf(event.actorName, event.createdAt).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) } } }
        }
    }
}

@Composable
private fun ProfileScreen(activity: MainActivity, initial: MfUser, billingMessage: String?, onUser: (MfUser) -> Unit, onBilling: () -> Unit, onResend: () -> Unit, onLogout: () -> Unit, onDelete: (String) -> Unit) {
    val api = remember { NativeApiClient() }; val scope = rememberCoroutineScope()
    var editing by remember { mutableStateOf(false) }; var user by remember(initial) { mutableStateOf(initial) }
    var name by remember { mutableStateOf(user.name) }; var street by remember { mutableStateOf(user.street) }; var postal by remember { mutableStateOf(user.postalCode) }; var city by remember { mutableStateOf(user.city) }; var country by remember { mutableStateOf(user.country.ifBlank { "Deutschland" }) }; var phone by remember { mutableStateOf(user.phone) }
    var deleteMode by remember { mutableStateOf(false) }; var password by remember { mutableStateOf("") }; var confirmation by remember { mutableStateOf("") }; var error by remember { mutableStateOf<String?>(null) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp, 20.dp, 16.dp, 30.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Text("Profil", fontSize = 32.sp, fontWeight = FontWeight.Bold) }
        item { MfCard { Row(verticalAlignment = Alignment.CenterVertically) { Surface(color = MfPrimary.copy(alpha = 0.12f), shape = CircleShape) { Text(initials(user.name), fontSize = 19.sp, fontWeight = FontWeight.Bold, color = MfPrimary, modifier = Modifier.padding(16.dp)) }; Column(Modifier.weight(1f).padding(start = 14.dp)) { Text(user.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold); Text(user.email, color = MaterialTheme.colorScheme.onSurfaceVariant) }; TextButton(onClick = { editing = !editing }) { Text(if (editing) "Schließen" else "Bearbeiten") } } } }
        if (editing) item { MfCard { SectionTitle("Deine Kontaktdaten", Icons.Default.Edit); MfField(name, { name = it }, "Name"); MfField(street, { street = it }, "Straße & Hausnummer"); Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { Box(Modifier.weight(0.38f)) { MfField(postal, { postal = it }, "PLZ") }; Box(Modifier.weight(0.62f)) { MfField(city, { city = it }, "Ort") } }; MfField(country, { country = it }, "Land"); MfField(phone, { phone = it }, "Telefon optional"); PrimaryButton("Profil speichern") { scope.launch { runCatching { api.updateProfile(name, street, postal, city, country, phone) }.onSuccess { user = it; onUser(it); editing = false }.onFailure { error = it.message } } } } }
        item { MfCard { Text("Konto", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); LabeledRow("Kontotyp", if (user.isManagement) "Hausverwaltung" else "Privat"); LabeledRow("Tarif", user.planLabel); LabeledRow("E-Mail bestätigt", if (user.emailVerified) "Ja" else "Nein"); if (!user.emailVerified) OutlinedButton(onClick = onResend, modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) { Text("Bestätigungs-E-Mail erneut senden") } } }
        item { MfCard { Text(if (user.isManagement) "Verwaltung" else "Privat Pro", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); Text("Unbegrenzte Vorgänge, erweiterte Belege, Fristen, Aufgaben, Kalender, Archiv und Auswertungen.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 8.dp)); PrimaryButton("Google-Play-Angebote ansehen", onClick = onBilling); billingMessage?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp)) } } }
        item { MfCard { Text("Konto & Datenschutz", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); LinkButton("Datenschutzerklärung") { activity.openUrl("https://maengelfix.kamilunavo.com/datenschutz") }; LinkButton("Nutzungsbedingungen (EULA)") { activity.openUrl("https://maengelfix.kamilunavo.com/nutzungsbedingungen") }; OutlinedButton(onClick = { deleteMode = !deleteMode }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) { Icon(Icons.Default.DeleteForever, null); Spacer(Modifier.width(8.dp)); Text("Konto dauerhaft löschen") } } }
        if (deleteMode) item { MfCard { Text("Konto dauerhaft löschen", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.error); Text("Diese Aktion kann nicht rückgängig gemacht werden.", color = MaterialTheme.colorScheme.onSurfaceVariant); MfField(password, { password = it }, "Aktuelles Passwort", true); MfField(confirmation, { confirmation = it }, "Zum Bestätigen LÖSCHEN eingeben"); PrimaryButton("Konto endgültig löschen", password.isNotBlank() && confirmation == "LÖSCHEN") { onDelete(password) } } }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item { OutlinedButton(onClick = onLogout, modifier = Modifier.fillMaxWidth().height(54.dp)) { Text("Abmelden", fontWeight = FontWeight.Bold) } }
        item { Text("MängelFix ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) · maengelfix.kamilunavo.com", style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth()) }
    }
}

@Composable private fun MfCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) { Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(14.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline), elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)) { Column(Modifier.padding(16.dp), content = content) } }
@Composable private fun PrimaryButton(label: String, enabled: Boolean = true, onClick: () -> Unit) { Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(13.dp)) { Text(label, fontWeight = FontWeight.Bold) } }
@Composable private fun SectionTitle(label: String, icon: ImageVector) { Row(verticalAlignment = Alignment.CenterVertically) { Icon(icon, null, tint = MfPrimary); Text(label, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 9.dp)) } }
@Composable private fun StatusBadge(label: String, done: Boolean) { Text(label, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = if (done) MfSuccess else MfPrimary) }
@Composable private fun Fact(icon: ImageVector, value: String) { if (value.isNotBlank()) Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) { Icon(icon, null, tint = MfPrimary, modifier = Modifier.size(19.dp)); Text(value, modifier = Modifier.padding(start = 8.dp)) } }
@Composable private fun EmptyText(text: String) { Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 12.dp)) }
@Composable private fun EmptyState(icon: ImageVector, title: String, text: String) { Column(Modifier.fillMaxWidth().padding(vertical = 70.dp), horizontalAlignment = Alignment.CenterHorizontally) { Surface(color = MfPrimary.copy(alpha = 0.1f), shape = RoundedCornerShape(22.dp)) { Icon(icon, null, tint = MfPrimary, modifier = Modifier.padding(22.dp).size(45.dp)) }; Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 16.dp)); Text(text, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp)) } }
@Composable private fun LabeledRow(label: String, value: String) { HorizontalDivider(Modifier.padding(vertical = 9.dp)); Row { Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f)); Text(value, fontWeight = FontWeight.SemiBold) } }
@Composable private fun LinkButton(label: String, onClick: () -> Unit) { TextButton(onClick = onClick, modifier = Modifier.fillMaxWidth()) { Text(label, modifier = Modifier.weight(1f), textAlign = TextAlign.Start); Text("→") } }
private fun initials(name: String) = name.split(" ").filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }.ifBlank { "MF" }

private fun MainActivity.readUpload(uri: Uri): UploadFile? = runCatching { val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@runCatching null; if (bytes.size > 12 * 1024 * 1024) return@runCatching null; val mime = contentResolver.getType(uri) ?: "image/jpeg"; UploadFile(bytes, "foto-${System.nanoTime()}.${if (mime.contains("png")) "png" else "jpg"}", mime) }.getOrNull()
private fun MainActivity.openUrl(url: String) { runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } }
private fun MainActivity.downloadPdf(api: NativeApiClient, caseId: String) { val request = DownloadManager.Request(Uri.parse(api.pdfUrl(caseId))).setTitle("MängelFix PDF").setDescription("Mängeldokumentation wird heruntergeladen").setMimeType("application/pdf").setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED).setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "maengelfix-${caseId.take(8)}.pdf"); api.cookieHeader().takeIf { it.isNotBlank() }?.let { request.addRequestHeader("Cookie", it) }; (getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request); Toast.makeText(this, "PDF wird heruntergeladen.", Toast.LENGTH_SHORT).show() }
