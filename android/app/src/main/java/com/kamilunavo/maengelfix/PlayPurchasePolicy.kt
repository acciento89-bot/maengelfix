package com.kamilunavo.maengelfix

internal object PlayPurchasePolicy {
    val restorableProductIds = listOf(
        "maengelfix.private.monthly", "maengelfix.private.yearly",
        "maengelfix.starter.monthly", "maengelfix.starter.yearly",
        "maengelfix.pro.monthly", "maengelfix.pro.yearly",
        "maengelfix.business.monthly", "maengelfix.business.yearly",
    )

    fun requiredAccountScope(productId: String): String? =
        when {
            productId !in restorableProductIds -> null
            productId.startsWith("maengelfix.private.") -> "private"
            else -> "organization"
        }

    // Keep the legacy annual ID restorable; Business is sold monthly only on Play.
    fun isOfferedForSale(productId: String): Boolean =
        productId in restorableProductIds && productId != "maengelfix.business.yearly"
}
