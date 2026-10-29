package com.kamilunavo.maengelfix

import org.junit.Assert.*
import org.junit.Test

class ProductIdentityAssetsTest {
    private fun request(
        path: String? = "/__android_identity__/property-dossier.css",
        scheme: String? = "https", host: String? = "maengelfix.kamilunavo.com",
        port: Int = -1, userInfo: String? = null, method: String? = "GET",
    ) = ProductIdentityAssets.resolve(scheme, host, port, userInfo, path, method)

    @Test fun ownsOnlyThreePackagedAssetsWithTheirCorrectMimeTypes() {
        assertEquals(ProductIdentityAsset("visual-identity/property-dossier.css", "text/css"), request())
        assertEquals(ProductIdentityAsset("fonts/cantarell/Cantarell-Regular.ttf", "font/ttf"), request("/__android_identity__/Cantarell-Regular.ttf"))
        assertEquals(ProductIdentityAsset("fonts/cantarell/Cantarell-Bold.ttf", "font/ttf"), request("/__android_identity__/Cantarell-Bold.ttf", port = 443))
    }

    @Test fun otherOriginsUserInfoAndNonDefaultPortsNeverReceiveLocalFiles() {
        for (host in listOf(null, "evil.example", "maengelfix.kamilunavo.com.evil.example", "kamilunavo.com")) assertNull(request(host = host))
        assertNull(request(scheme = "http"))
        assertNull(request(port = 8443))
        assertNull(request(userInfo = "user"))
    }

    @Test fun unrelatedFilesApiAuthBillingAndMutatingMethodsPassThrough() {
        for (path in listOf(null, "/app", "/api/auth/login", "/auth/callback", "/api/billing/checkout", "/__android_identity__/../secrets", "/__android_identity__/OFL.txt", "/__android_identity__/Cantarell-Regular.ttf/extra")) assertNull(request(path))
        for (method in listOf(null, "POST", "PUT", "DELETE", "HEAD")) assertNull(request(method = method))
    }
}
