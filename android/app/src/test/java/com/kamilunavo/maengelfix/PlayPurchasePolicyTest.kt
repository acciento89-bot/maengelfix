package com.kamilunavo.maengelfix

import org.junit.Assert.*
import org.junit.Test

class PlayPurchasePolicyTest {
    @Test fun privateOffersRequireAPrivateAccount() {
        for (id in listOf("maengelfix.private.monthly", "maengelfix.private.yearly")) {
            assertEquals(id, "private", PlayPurchasePolicy.requiredAccountScope(id))
        }
    }

    @Test fun managementOffersRequireAnOrganizationAccount() {
        for (id in listOf(
            "maengelfix.starter.monthly", "maengelfix.starter.yearly",
            "maengelfix.pro.monthly", "maengelfix.pro.yearly",
            "maengelfix.business.monthly", "maengelfix.business.yearly",
        )) {
            assertEquals(id, "organization", PlayPurchasePolicy.requiredAccountScope(id))
        }
    }

    @Test fun businessIsOfferedMonthlyOnly() {
        assertTrue(PlayPurchasePolicy.isOfferedForSale("maengelfix.business.monthly"))
        assertFalse(PlayPurchasePolicy.isOfferedForSale("maengelfix.business.yearly"))
    }

    @Test fun withdrawingAnOfferDoesNotDiscardRestorableEntitlements() {
        assertTrue("maengelfix.business.yearly" in PlayPurchasePolicy.restorableProductIds)
        assertEquals("organization", PlayPurchasePolicy.requiredAccountScope("maengelfix.business.yearly"))
    }

    @Test fun unknownProductCannotBecomeAPrivateOfferByDefault() {
        for (id in listOf("", "maengelfix.other.monthly", "anotherapp.private.monthly")) {
            assertNull(id, PlayPurchasePolicy.requiredAccountScope(id))
            assertFalse(id, PlayPurchasePolicy.isOfferedForSale(id))
        }
    }

    @Test fun otherExistingPlansRemainAvailableInBothPeriods() {
        for (id in listOf("maengelfix.private.monthly", "maengelfix.private.yearly",
            "maengelfix.starter.monthly", "maengelfix.starter.yearly",
            "maengelfix.pro.monthly", "maengelfix.pro.yearly")) {
            assertTrue(id, PlayPurchasePolicy.isOfferedForSale(id))
        }
    }
}
