package com.kamilunavo.maengelfix

import android.webkit.CookieManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class NativeApiClient {
    private val baseUrl = "https://${BuildConfig.ALLOWED_HOST}"
    private val cookies = CookieManager.getInstance().apply { setAcceptCookie(true) }

    suspend fun me() = user(request("/api/me").getJSONObject("user"))
    suspend fun login(email: String, password: String) = user(request("/api/auth/login", "POST", JSONObject().put("email", email).put("password", password)).getJSONObject("user"))
    suspend fun register(name: String, email: String, password: String, accountType: String, organizationName: String?) = user(
        request("/api/auth/register", "POST", JSONObject().put("name", name).put("email", email).put("password", password).put("accountType", accountType).apply { organizationName?.let { put("organizationName", it) } }).getJSONObject("user")
    )
    suspend fun forgot(email: String): String = request("/api/auth/forgot-password", "POST", JSONObject().put("email", email)).optString("message", "Wenn ein Konto existiert, wurde eine E-Mail versendet.")
    suspend fun resendVerification() { request("/api/auth/resend-verification", "POST", JSONObject()) }
    suspend fun logout() { runCatching { request("/api/auth/logout", "POST", JSONObject()) }; cookies.removeAllCookies(null); cookies.flush() }
    suspend fun cases(): List<DefectCase> = request("/api/cases").getJSONArray("cases").mapObjects(::defectCase)
    suspend fun caseDetail(id: String): CaseDetail {
        val root = request("/api/cases/$id")
        return CaseDetail(
            defectCase(root.getJSONObject("case")),
            root.optJSONArray("events").orEmpty().mapObjects { CaseEvent(it.getString("id"), it.optString("note"), it.optString("actor_name", it.optString("actorName")), it.optString("created_at", it.optString("createdAt"))) },
            root.optJSONArray("attachments").orEmpty().mapObjects { CaseAttachment(it.getString("id"), it.optString("original_name", it.optString("originalName")), it.optString("mime_type", it.optString("mimeType"))) },
            root.optJSONArray("messages").orEmpty().mapObjects { CaseMessage(it.getString("id"), it.optString("message"), it.optString("actor_name", it.optString("actorName")), it.optString("created_at", it.optString("createdAt"))) },
        )
    }
    suspend fun createCase(fields: Map<String, String?>): DefectCase {
        val body = JSONObject(); fields.forEach { (key, value) -> if (!value.isNullOrBlank()) body.put(key, value) }
        return defectCase(request("/api/cases", "POST", body).getJSONObject("case"))
    }
    suspend fun updateCase(id: String, fields: Map<String, String?>): DefectCase {
        val body = JSONObject(); fields.forEach { (key, value) -> body.put(key, value ?: JSONObject.NULL) }
        return defectCase(request("/api/cases/$id", "PATCH", body).getJSONObject("case"))
    }
    suspend fun sendMessage(id: String, message: String) { request("/api/cases/$id/messages", "POST", JSONObject().put("message", message)) }
    suspend fun updateProfile(name: String, street: String, postalCode: String, city: String, country: String, phone: String): MfUser = user(
        request("/api/profile", "PATCH", JSONObject().put("name", name).put("street", street).put("postalCode", postalCode).put("city", city).put("country", country).put("phone", phone)).getJSONObject("user")
    )
    suspend fun deleteAccount(password: String) { request("/api/account", "DELETE", JSONObject().put("password", password).put("confirmation", "DELETE")); cookies.removeAllCookies(null); cookies.flush() }
    suspend fun managementOverview(): ManagementOverview {
        val root = request("/api/management/overview")
        val org = root.optJSONObject("organization") ?: JSONObject()
        val m = root.optJSONObject("metrics") ?: JSONObject()
        return ManagementOverview(
            org.optString("name", "MängelFix Verwaltung"),
            ManagementMetrics(m.optInt("properties"), m.optInt("units"), m.optInt("contacts"), m.optInt("open"), m.optInt("unassigned"), m.optInt("overdue")),
            root.optJSONArray("recent").orEmpty().mapObjects(::defectCase),
            root.optJSONArray("members").orEmpty().mapObjects { ManagementMember(it.getString("id"), it.optString("name"), it.optString("role"), it.optInt("open_cases", it.optInt("openCases"))) },
        )
    }

    suspend fun uploadImages(caseId: String, files: List<UploadFile>) = withContext(Dispatchers.IO) {
        if (files.isEmpty()) return@withContext
        val boundary = "MaengelFix-${UUID.randomUUID()}"
        val out = ByteArrayOutputStream()
        fun write(value: String) = out.write(value.toByteArray())
        files.take(5).forEach { file ->
            write("--$boundary\r\nContent-Disposition: form-data; name=\"images\"; filename=\"${file.fileName.replace("\"", "")}\"\r\nContent-Type: ${file.mimeType}\r\n\r\n")
            out.write(file.bytes); write("\r\n")
        }
        write("--$boundary--\r\n")
        execute("/api/cases/$caseId/attachments", "POST", "multipart/form-data; boundary=$boundary", out.toByteArray())
    }

    fun cookieHeader(): String = cookies.getCookie(baseUrl).orEmpty()
    fun attachmentUrl(id: String) = "$baseUrl/api/attachments/$id"
    fun pdfUrl(id: String) = "$baseUrl/api/cases/$id/pdf?download=1"

    private suspend fun request(path: String, method: String = "GET", json: JSONObject? = null): JSONObject = execute(path, method, json?.let { "application/json" }, json?.toString()?.toByteArray())
    private suspend fun execute(path: String, method: String, contentType: String?, body: ByteArray?): JSONObject = withContext(Dispatchers.IO) {
        val url = "$baseUrl$path"
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method; connectTimeout = 30_000; readTimeout = 120_000; useCaches = false
            setRequestProperty("Accept", "application/json"); setRequestProperty("X-MaengelFix-Client", "MängelFix-Android/${BuildConfig.VERSION_NAME}")
            cookies.getCookie(url)?.let { setRequestProperty("Cookie", it) }
            contentType?.let { setRequestProperty("Content-Type", it) }
            if (body != null) { doOutput = true; setFixedLengthStreamingMode(body.size) }
        }
        try {
            body?.let { connection.outputStream.use { stream -> stream.write(it) } }
            val status = connection.responseCode
            connection.headerFields.entries.filter { it.key?.equals("Set-Cookie", true) == true }.flatMap { it.value.orEmpty() }.forEach { cookies.setCookie(baseUrl, it) }
            cookies.flush()
            val bytes = (if (status in 200..299) connection.inputStream else connection.errorStream)?.use { it.readBytes() } ?: ByteArray(0)
            val text = bytes.toString(Charsets.UTF_8)
            if (status !in 200..299) throw NativeApiException(runCatching { JSONObject(text).optString("error") }.getOrNull().orEmpty().ifBlank { "MängelFix konnte die Anfrage nicht abschließen." }, status)
            if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally { connection.disconnect() }
    }

    private fun user(j: JSONObject) = MfUser(j.getString("id"), j.optString("name"), j.optString("email"), j.optString("street"), j.optString("postal_code", j.optString("postalCode")), j.optString("city"), j.optString("country", "Deutschland"), j.optString("phone"), j.optBoolean("email_verified", j.optBoolean("emailVerified")), j.optString("plan_code", j.optString("planCode", "private_free")), j.optString("subscription_status", j.optString("subscriptionStatus")), j.optString("onboarding_use_case", j.optString("onboardingUseCase")).takeIf { it.isNotBlank() })
    private fun defectCase(j: JSONObject) = DefectCase(j.getString("id"), j.optString("title"), j.optString("category"), j.optString("description"), j.optString("property_label", j.optString("propertyLabel")), j.optString("location_label", j.optString("locationLabel")), j.optString("discovered_on", j.optString("discoveredOn")), j.optString("recipient_name", j.optString("recipientName")), j.optString("recipient_email", j.optString("recipientEmail")), j.optString("recipient_address", j.optString("recipientAddress")), j.optString("deadline_on", j.optString("deadlineOn")), j.optString("status"), j.optString("case_context", j.optString("caseContext")), j.optInt("attachment_count", j.optInt("attachmentCount")), j.optBoolean("submitted_by_tenant", j.optBoolean("submittedByTenant")), if (j.isNull("archived_at") && j.isNull("archivedAt")) null else j.optString("archived_at", j.optString("archivedAt")).takeIf { it.isNotBlank() })
}

class NativeApiException(message: String, val statusCode: Int) : Exception(message)
private fun JSONArray?.orEmpty() = this ?: JSONArray()
private fun <T> JSONArray.mapObjects(block: (JSONObject) -> T) = List(length()) { block(getJSONObject(it)) }
