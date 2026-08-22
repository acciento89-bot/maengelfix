# MängelFix Android client relies on platform WebView and AndroidX/Compose consumer rules.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
