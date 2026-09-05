package com.kamilunavo.maengelfix

data class MfUser(
    val id: String,
    val name: String,
    val email: String,
    val street: String,
    val postalCode: String,
    val city: String,
    val country: String,
    val phone: String,
    val emailVerified: Boolean,
    val planCode: String,
    val subscriptionStatus: String,
    val onboardingUseCase: String?,
) {
    val isManagement: Boolean get() = onboardingUseCase == "management" || planCode.startsWith("management_")
    val planLabel: String get() = when (planCode) {
        "private_pro" -> "Privat Pro"
        "private_free" -> "Privat Free"
        "management_trial" -> "Verwaltung · Testphase"
        "management_starter" -> "Verwaltung Starter"
        "management_pro" -> "Verwaltung Pro"
        "management_business" -> "Verwaltung Business"
        else -> planCode.replace('_', ' ').replaceFirstChar { it.uppercase() }
    }
}

data class DefectCase(
    val id: String,
    val title: String,
    val category: String,
    val description: String,
    val propertyLabel: String,
    val locationLabel: String,
    val discoveredOn: String,
    val recipientName: String,
    val recipientEmail: String,
    val recipientAddress: String,
    val deadlineOn: String,
    val status: String,
    val caseContext: String,
    val attachmentCount: Int,
    val submittedByTenant: Boolean,
    val archivedAt: String?,
) {
    val statusLabel: String get() = when (status) {
        "draft" -> "Entwurf"
        "sent" -> "Versendet"
        "reply" -> "Rückmeldung"
        "received" -> "Eingegangen"
        "reviewing" -> "In Prüfung"
        "commissioned" -> "Beauftragt"
        "scheduled" -> "Terminiert"
        "in_progress" -> "In Bearbeitung"
        "resolved" -> "Erledigt"
        else -> status.replace('_', ' ').replaceFirstChar { it.uppercase() }
    }
}

data class CaseEvent(val id: String, val note: String, val actorName: String, val createdAt: String)
data class CaseAttachment(val id: String, val originalName: String, val mimeType: String)
data class CaseMessage(val id: String, val message: String, val actorName: String, val createdAt: String)
data class CaseDetail(val caseItem: DefectCase, val events: List<CaseEvent>, val attachments: List<CaseAttachment>, val messages: List<CaseMessage>)
data class UploadFile(val bytes: ByteArray, val fileName: String, val mimeType: String)

data class ManagementMetrics(val properties: Int, val units: Int, val contacts: Int, val open: Int, val unassigned: Int, val overdue: Int)
data class ManagementMember(val id: String, val name: String, val role: String, val openCases: Int)
data class ManagementOverview(val organizationName: String, val metrics: ManagementMetrics, val recent: List<DefectCase>, val members: List<ManagementMember>)
