package com.kamilunavo.maengelfix

/** Visual styling scope only. Does not authorize navigation or authentication. */
internal object ProductIdentityPages {
    val authPaths: List<String> = listOf(
        "/anmelden",
        "/registrieren",
        "/registrieren/privat",
        "/registrieren/verwaltung",
    )

    fun isAllowed(path: String?): Boolean =
        path == "/app" || path.orEmpty().startsWith("/app/") || (path != null && path in authPaths)

    // Constants only: use the same exact form allowlist in the native and DOM checks.
    fun authPathsJson(): String = authPaths.joinToString(prefix = "[", postfix = "]") { "\"$it\"" }
}
