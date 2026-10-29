package com.kamilunavo.maengelfix

import org.junit.Assert.*
import org.junit.Test

class ProductIdentityPagesTest {
    @Test fun acceptsOnlyExistingWorkspaceAndFourExactOwnForms() {
        for (path in listOf("/app", "/app/cases/42", "/anmelden", "/registrieren", "/registrieren/privat", "/registrieren/verwaltung")) {
            assertTrue(path, ProductIdentityPages.isAllowed(path))
        }
    }

    @Test fun excludesProviderApiCallbackLegalAndLookalikePaths() {
        for (path in listOf("/api/auth/login", "/auth/callback", "/impressum", "/datenschutz", "/nutzungsbedingungen", "/anmelden/", "/Anmelden", "/registrieren/provider", "/app-provider", "/passwort-vergessen", "/%61nmelden", "")) {
            assertFalse(path, ProductIdentityPages.isAllowed(path))
        }
        assertFalse(ProductIdentityPages.isAllowed(null))
    }

    @Test fun domAllowlistUsesTheSameFourConstants() {
        assertEquals(4, ProductIdentityPages.authPaths.size)
        assertEquals("[\"/anmelden\", \"/registrieren\", \"/registrieren/privat\", \"/registrieren/verwaltung\"]", ProductIdentityPages.authPathsJson())
    }
}
