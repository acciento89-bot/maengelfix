package com.kamilunavo.maengelfix

import androidx.compose.material3.Typography
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontSynthesis
import androidx.compose.ui.text.font.FontWeight

// Original Cantarell faces. The bundled OFL accompanies these immutable assets.
private val ProductFont = FontFamily(
    Font(R.font.brand_regular, FontWeight.Normal),
    Font(R.font.brand_bold, FontWeight.Bold)
)

// Retain each screen's type scale; do not synthesize unavailable font faces.
internal fun brandedTypography(base: Typography = Typography()): Typography = base.copy(
    displayLarge = base.displayLarge.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    displayMedium = base.displayMedium.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    displaySmall = base.displaySmall.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    headlineLarge = base.headlineLarge.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    headlineMedium = base.headlineMedium.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    headlineSmall = base.headlineSmall.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    titleLarge = base.titleLarge.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    titleMedium = base.titleMedium.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    titleSmall = base.titleSmall.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    bodyLarge = base.bodyLarge.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    bodyMedium = base.bodyMedium.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    bodySmall = base.bodySmall.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    labelLarge = base.labelLarge.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    labelMedium = base.labelMedium.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None),
    labelSmall = base.labelSmall.copy(fontFamily = ProductFont, fontSynthesis = FontSynthesis.None)
)
