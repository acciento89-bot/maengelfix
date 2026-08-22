package com.kamilunavo.maengelfix

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private data class PlayPlan(
    val title: String,
    val subtitle: String,
    val monthlyId: String,
    val yearlyId: String,
)

private val playPlans = listOf(
    PlayPlan(
        title = "Privat Pro",
        subtitle = "Für private Mängelfälle und erweiterte Dokumentation",
        monthlyId = "com.kamilunavo.maengelfix.privatepro.monthly",
        yearlyId = "com.kamilunavo.maengelfix.privatepro.yearly",
    ),
    PlayPlan(
        title = "Management Starter",
        subtitle = "Für kleinere Hausverwaltungen",
        monthlyId = "com.kamilunavo.maengelfix.managementstarter.monthly",
        yearlyId = "com.kamilunavo.maengelfix.managementstarter.yearly",
    ),
    PlayPlan(
        title = "Management Pro",
        subtitle = "Für wachsende Verwaltungs-Teams",
        monthlyId = "com.kamilunavo.maengelfix.managementpro.monthly",
        yearlyId = "com.kamilunavo.maengelfix.managementpro.yearly",
    ),
    PlayPlan(
        title = "Management Business",
        subtitle = "Für größere Organisationen und Teams",
        monthlyId = "com.kamilunavo.maengelfix.managementbusiness.monthly",
        yearlyId = "com.kamilunavo.maengelfix.managementbusiness.yearly",
    ),
)

@Composable
fun PlayBillingSheet(
    billing: BillingManager,
    catalogVersion: Int,
    onClose: () -> Unit,
) {
    // catalogVersion intentionally makes Compose observe native BillingClient catalog refreshes.
    @Suppress("UNUSED_VARIABLE") val refreshMarker = catalogVersion

    Surface(modifier = Modifier.fillMaxSize(), tonalElevation = 6.dp) {
        Column(Modifier.fillMaxSize().padding(20.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("MängelFix über Google Play", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text("Preise werden direkt aus Google Play geladen.", style = MaterialTheme.typography.bodyMedium)
                }
                TextButton(onClick = onClose) { Text("Schließen") }
            }

            Spacer(Modifier.height(12.dp))

            LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.weight(1f)) {
                items(playPlans.size) { index ->
                    val plan = playPlans[index]
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Text(plan.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            Text(plan.subtitle, modifier = Modifier.padding(top = 4.dp, bottom = 12.dp))
                            Button(
                                onClick = { billing.purchase(plan.monthlyId) },
                                modifier = Modifier.fillMaxWidth(),
                                enabled = billing.isReady() && billing.price(plan.monthlyId) != null,
                            ) {
                                Text("Monatlich · ${billing.price(plan.monthlyId) ?: "wird geladen"}")
                            }
                            OutlinedButton(
                                onClick = { billing.purchase(plan.yearlyId) },
                                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                                enabled = billing.isReady() && billing.price(plan.yearlyId) != null,
                            ) {
                                Text("Jährlich · ${billing.price(plan.yearlyId) ?: "wird geladen"}")
                            }
                        }
                    }
                }
            }

            OutlinedButton(
                onClick = billing::restorePurchases,
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            ) { Text("Käufe wiederherstellen") }

            Text(
                "Abos verlängern sich automatisch und können in Google Play verwaltet oder gekündigt werden. MängelFix startet kein zweites Abo, solange für dein Konto bereits ein aktives Abo über Google Play, Apple oder MängelFix Web besteht.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 12.dp),
            )
        }
    }
}
