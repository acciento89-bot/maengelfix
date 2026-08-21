package com.kamilunavo.maengelfix

import android.app.Activity
import android.webkit.CookieManager
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class BillingManager(
    private val activity: Activity,
    private val onCatalogChanged: () -> Unit,
    private val onVerified: () -> Unit,
    private val onMessage: (String) -> Unit,
) : PurchasesUpdatedListener {

    companion object {
        val productIds = listOf(
            "com.kamilunavo.maengelfix.privatepro.monthly",
            "com.kamilunavo.maengelfix.privatepro.yearly",
            "com.kamilunavo.maengelfix.managementstarter.monthly",
            "com.kamilunavo.maengelfix.managementstarter.yearly",
            "com.kamilunavo.maengelfix.managementpro.monthly",
            "com.kamilunavo.maengelfix.managementpro.yearly",
            "com.kamilunavo.maengelfix.managementbusiness.monthly",
            "com.kamilunavo.maengelfix.managementbusiness.yearly",
        )
        private val knownProducts = productIds.toSet()
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val details = mutableMapOf<String, ProductDetails>()
    private var ready = false

    private val billingClient = BillingClient.newBuilder(activity.applicationContext)
        .setListener(this)
        .enablePendingPurchases(
            PendingPurchasesParams.newBuilder()
                .enableOneTimeProducts()
                .build()
        )
        .enableAutoServiceReconnection()
        .build()

    init {
        connect()
    }

    fun close() {
        billingClient.endConnection()
    }

    fun catalogJson(): String {
        val products = JSONArray()
        productIds.forEach { id ->
            val detail = details[id]
            val offer = detail?.subscriptionOfferDetails.orEmpty()
                .firstOrNull { it.offerId == null }
                ?: detail?.subscriptionOfferDetails.orEmpty().firstOrNull()
            val price = offer?.pricingPhases?.pricingPhaseList?.lastOrNull()?.formattedPrice
            products.put(
                JSONObject()
                    .put("id", id)
                    .put("price", price ?: JSONObject.NULL)
            )
        }
        return JSONObject()
            .put("ready", ready)
            .put("products", products)
            .toString()
    }

    fun purchase(productId: String) {
        if (productId !in knownProducts) {
            onMessage("Unbekanntes MängelFix Google-Play-Abo.")
            return
        }
        val detail = details[productId]
        if (!ready || detail == null) {
            onMessage("Google Play lädt die Abo-Angebote noch. Bitte versuche es gleich erneut.")
            queryProducts()
            return
        }

        scope.launch {
            try {
                val accountHash = fetchAuthenticatedAccountHash()
                val offer = detail.subscriptionOfferDetails.orEmpty()
                    .firstOrNull { it.offerId == null }
                    ?: detail.subscriptionOfferDetails.orEmpty().firstOrNull()
                    ?: throw IllegalStateException("Für dieses Abo ist kein aktiver Google-Play-Base-Plan verfügbar.")

                val productParams = BillingFlowParams.ProductDetailsParams.newBuilder()
                    .setProductDetails(detail)
                    .setOfferToken(offer.offerToken)
                    .build()
                val flow = BillingFlowParams.newBuilder()
                    .setProductDetailsParamsList(listOf(productParams))
                    .setObfuscatedAccountId(accountHash)
                    .build()
                val result = billingClient.launchBillingFlow(activity, flow)
                if (result.responseCode != BillingClient.BillingResponseCode.OK) {
                    onMessage(result.debugMessage.ifBlank { "Der Google-Play-Kauf konnte nicht gestartet werden." })
                }
            } catch (error: Exception) {
                onMessage(error.message ?: "Der Google-Play-Kauf konnte nicht vorbereitet werden.")
            }
        }
    }

    fun restorePurchases() {
        if (!billingClient.isReady) {
            connect()
            return
        }
        val params = QueryPurchasesParams.newBuilder()
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
        billingClient.queryPurchasesAsync(params) { result, purchases ->
            if (result.responseCode != BillingClient.BillingResponseCode.OK) {
                onMessage(result.debugMessage.ifBlank { "Google-Play-Käufe konnten nicht wiederhergestellt werden." })
                return@queryPurchasesAsync
            }
            val owned = purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED && it.products.any(knownProducts::contains) }
            if (owned.isEmpty()) {
                onMessage("Es wurde kein aktives MängelFix-Abo in Google Play gefunden.")
                return@queryPurchasesAsync
            }
            owned.forEach(::verifyAndAcknowledge)
        }
    }

    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) {
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK -> purchases.orEmpty().forEach { purchase ->
                when (purchase.purchaseState) {
                    Purchase.PurchaseState.PURCHASED -> verifyAndAcknowledge(purchase)
                    Purchase.PurchaseState.PENDING -> onMessage("Der Google-Play-Kauf wartet noch auf Zahlungsbestätigung.")
                }
            }
            BillingClient.BillingResponseCode.USER_CANCELED -> Unit
            BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED -> restorePurchases()
            else -> onMessage(result.debugMessage.ifBlank { "Der Google-Play-Kauf konnte nicht abgeschlossen werden." })
        }
    }

    private fun connect() {
        if (billingClient.isReady) {
            ready = true
            queryProducts()
            return
        }
        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                ready = result.responseCode == BillingClient.BillingResponseCode.OK
                if (ready) queryProducts()
                else onMessage(result.debugMessage.ifBlank { "Google Play Billing ist gerade nicht verfügbar." })
                onCatalogChanged()
            }

            override fun onBillingServiceDisconnected() {
                ready = false
                onCatalogChanged()
            }
        })
    }

    private fun queryProducts() {
        if (!billingClient.isReady) return
        val products = productIds.map { id ->
            QueryProductDetailsParams.Product.newBuilder()
                .setProductId(id)
                .setProductType(BillingClient.ProductType.SUBS)
                .build()
        }
        billingClient.queryProductDetailsAsync(
            QueryProductDetailsParams.newBuilder().setProductList(products).build()
        ) { result, queryResult ->
            details.clear()
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                queryResult.productDetailsList.forEach { details[it.productId] = it }
                ready = true
            } else {
                ready = false
            }
            onCatalogChanged()
        }
    }

    private fun verifyAndAcknowledge(purchase: Purchase) {
        val productId = purchase.products.firstOrNull(knownProducts::contains) ?: return
        scope.launch {
            try {
                verifyWithServer(productId, purchase.purchaseToken)
                if (!purchase.isAcknowledged) {
                    val params = AcknowledgePurchaseParams.newBuilder()
                        .setPurchaseToken(purchase.purchaseToken)
                        .build()
                    billingClient.acknowledgePurchase(params) { result ->
                        if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                            onVerified()
                            onMessage("MängelFix-Abo wurde über Google Play aktiviert.")
                        } else {
                            onMessage("Kauf wurde bestätigt, konnte aber noch nicht bei Google quittiert werden. Bitte Käufe wiederherstellen.")
                        }
                    }
                } else {
                    onVerified()
                    onMessage("MängelFix-Abo wurde über Google Play bestätigt.")
                }
            } catch (error: Exception) {
                onMessage(error.message ?: "Der Google-Play-Kauf konnte serverseitig nicht bestätigt werden.")
            }
        }
    }

    private suspend fun fetchAuthenticatedAccountHash(): String = withContext(Dispatchers.IO) {
        val connection = authenticatedConnection("/api/auth/me", "GET")
        try {
            val status = connection.responseCode
            val bytes = (if (status in 200..299) connection.inputStream else connection.errorStream)?.use { it.readBytes() } ?: ByteArray(0)
            if (status !in 200..299) throw IllegalStateException("Bitte melde dich in MängelFix erneut an, bevor du ein Abo kaufst.")
            val root = JSONObject(bytes.toString(Charsets.UTF_8))
            val userId = root.optJSONObject("user")?.optString("id").orEmpty()
            if (userId.isBlank()) throw IllegalStateException("MängelFix-Konto konnte nicht sicher bestimmt werden.")
            MessageDigest.getInstance("SHA-256")
                .digest(userId.lowercase().toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
        } finally {
            connection.disconnect()
        }
    }

    private suspend fun verifyWithServer(productId: String, purchaseToken: String) = withContext(Dispatchers.IO) {
        val connection = authenticatedConnection("/api/billing/google-play/verify", "POST")
        try {
            val body = JSONObject()
                .put("productId", productId)
                .put("purchaseToken", purchaseToken)
                .toString()
                .toByteArray(Charsets.UTF_8)
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setFixedLengthStreamingMode(body.size)
            connection.outputStream.use { it.write(body) }
            val status = connection.responseCode
            val bytes = (if (status in 200..299) connection.inputStream else connection.errorStream)?.use { it.readBytes() } ?: ByteArray(0)
            if (status !in 200..299) {
                val text = bytes.toString(Charsets.UTF_8)
                val message = runCatching { JSONObject(text).optString("error") }.getOrNull().orEmpty()
                throw IllegalStateException(message.ifBlank { "Google-Play-Kauf wurde vom MängelFix-Server nicht bestätigt." })
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun authenticatedConnection(path: String, method: String): HttpURLConnection {
        val url = URL("https://${BuildConfig.ALLOWED_HOST}$path")
        return (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 30_000
            readTimeout = 60_000
            useCaches = false
            setRequestProperty("Accept", "application/json")
            CookieManager.getInstance().getCookie(url.toString())?.takeIf { it.isNotBlank() }?.let {
                setRequestProperty("Cookie", it)
            }
        }
    }
}
