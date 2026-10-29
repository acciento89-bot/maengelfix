package com.kamilunavo.maengelfix

internal data class ProductIdentityAsset(val assetPath: String, val mimeType: String)

/** The same tiny allowlist serves ordinary WebView and service-worker requests. */
internal object ProductIdentityAssets {
    fun resolve(
        scheme: String?, host: String?, port: Int, userInfo: String?,
        path: String?, method: String?,
    ): ProductIdentityAsset? {
        if (scheme != "https" || host != BuildConfig.ALLOWED_HOST ||
            (port != -1 && port != 443) || userInfo != null || method != "GET") return null
        return when (path) {
            "/__android_identity__/property-dossier.css" ->
                ProductIdentityAsset("visual-identity/property-dossier.css", "text/css")
            "/__android_identity__/Cantarell-Regular.ttf" ->
                ProductIdentityAsset("fonts/cantarell/Cantarell-Regular.ttf", "font/ttf")
            "/__android_identity__/Cantarell-Bold.ttf" ->
                ProductIdentityAsset("fonts/cantarell/Cantarell-Bold.ttf", "font/ttf")
            else -> null
        }
    }
}
