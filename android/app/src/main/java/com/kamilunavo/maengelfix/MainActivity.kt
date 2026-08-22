package com.kamilunavo.maengelfix

import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.MimeTypeMap
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import java.io.ByteArrayInputStream

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaengelFixApp(this) }
    }
}

@Composable
private fun MaengelFixApp(activity: MainActivity) {
    var webView by remember { mutableStateOf<WebView?>(null) }
    var loading by remember { mutableStateOf(true) }
    var fatalError by remember { mutableStateOf<String?>(null) }
    var pendingFileCallback by remember { mutableStateOf<ValueCallback<Array<Uri>>?>(null) }
    var showPlayBilling by remember { mutableStateOf(false) }
    var billingCatalogVersion by remember { mutableStateOf(0) }

    val billingManager = remember(activity) {
        BillingManager(
            activity = activity,
            onCatalogChanged = {
                activity.runOnUiThread { billingCatalogVersion += 1 }
            },
            onVerified = {
                activity.runOnUiThread {
                    showPlayBilling = false
                    webView?.reload()
                }
            },
            onMessage = { message ->
                activity.runOnUiThread {
                    Toast.makeText(activity, message, Toast.LENGTH_LONG).show()
                }
            },
        )
    }

    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val callback = pendingFileCallback ?: return@rememberLauncherForActivityResult
        pendingFileCallback = null
        if (result.resultCode != Activity.RESULT_OK) {
            callback.onReceiveValue(null)
            return@rememberLauncherForActivityResult
        }

        val data = result.data
        val uris = when {
            data?.clipData != null -> Array(data.clipData!!.itemCount) { index ->
                data.clipData!!.getItemAt(index).uri
            }
            data?.data != null -> arrayOf(data.data!!)
            else -> null
        }
        callback.onReceiveValue(uris)
    }

    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Color(0xFF1769E0),
            background = Color(0xFFF5F7FA),
            surface = Color.White,
            onBackground = Color(0xFF101828),
            onSurface = Color(0xFF101828),
        )
    ) {
        Box(Modifier.fillMaxSize().statusBarsPadding()) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { context ->
                    WebView(context).apply {
                        webView = this
                        configureMaengelFixWebView(
                            activity = activity,
                            onLoading = { loading = it },
                            onFatalError = { fatalError = it },
                            onOpenPlayBilling = { showPlayBilling = true },
                            onFileChooser = { callback, params ->
                                pendingFileCallback?.onReceiveValue(null)
                                pendingFileCallback = callback
                                val acceptTypes = params.acceptTypes.filter { it.isNotBlank() }.toTypedArray()
                                val chooser = Intent(Intent.ACTION_GET_CONTENT).apply {
                                    addCategory(Intent.CATEGORY_OPENABLE)
                                    type = if (acceptTypes.size == 1) acceptTypes[0] else "*/*"
                                    if (acceptTypes.size > 1) putExtra(Intent.EXTRA_MIME_TYPES, acceptTypes)
                                    putExtra(
                                        Intent.EXTRA_ALLOW_MULTIPLE,
                                        params.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE,
                                    )
                                }
                                filePicker.launch(Intent.createChooser(chooser, "Datei oder Foto auswählen"))
                            },
                        )
                        val deepLink = activity.intent?.data?.takeIf {
                            it.scheme == "https" && it.host.equals(BuildConfig.ALLOWED_HOST, ignoreCase = true)
                        }
                        loadUrl(deepLink?.toString() ?: BuildConfig.APP_URL)
                    }
                },
                update = { webView = it },
            )

            if (loading && fatalError == null && !showPlayBilling) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = Color(0xFF1769E0),
                )
            }

            fatalError?.let { message ->
                Column(
                    modifier = Modifier.align(Alignment.Center).padding(28.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("MängelFix konnte nicht geladen werden.")
                    Text(
                        message,
                        modifier = Modifier.padding(top = 8.dp, bottom = 18.dp),
                        color = Color(0xFF667085),
                    )
                    Button(
                        onClick = {
                            fatalError = null
                            loading = true
                            webView?.reload()
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Erneut versuchen")
                    }
                }
            }

            if (showPlayBilling) {
                PlayBillingSheet(
                    billing = billingManager,
                    catalogVersion = billingCatalogVersion,
                    onClose = { showPlayBilling = false },
                )
            }
        }
    }

    BackHandler {
        if (showPlayBilling) {
            showPlayBilling = false
        } else {
            webView?.evaluateJavascript(
                """
                (() => {
                  const modalClose = document.querySelector('.modalBackdrop .iconButton');
                  if (modalClose) { modalClose.click(); return 'handled'; }
                  const backButton = document.querySelector('.backButton');
                  if (backButton) { backButton.click(); return 'handled'; }
                  const navButtons = [...document.querySelectorAll('.workspaceSidebar nav button')];
                  const active = navButtons.find(button => button.classList.contains('active'));
                  const overview = navButtons.find(button => button.textContent?.includes('Übersicht'));
                  if (overview && active !== overview) { overview.click(); return 'handled'; }
                  return 'root';
                })();
                """.trimIndent(),
            ) { result ->
                if (result?.contains("root") == true) activity.moveTaskToBack(true)
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            billingManager.close()
            pendingFileCallback?.onReceiveValue(null)
            webView?.apply {
                stopLoading()
                loadUrl("about:blank")
                clearHistory()
                removeAllViews()
                destroy()
            }
        }
    }
}

private fun WebView.configureMaengelFixWebView(
    activity: MainActivity,
    onLoading: (Boolean) -> Unit,
    onFatalError: (String?) -> Unit,
    onOpenPlayBilling: () -> Unit,
    onFileChooser: (ValueCallback<Array<Uri>>, WebChromeClient.FileChooserParams) -> Unit,
) {
    setBackgroundColor(android.graphics.Color.WHITE)
    settings.apply {
        javaScriptEnabled = true
        domStorageEnabled = true
        databaseEnabled = true
        cacheMode = WebSettings.LOAD_DEFAULT
        mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        allowFileAccess = false
        allowContentAccess = true
        javaScriptCanOpenWindowsAutomatically = false
        setSupportMultipleWindows(false)
        userAgentString = "$userAgentString MaengelFixAndroid/${BuildConfig.VERSION_NAME}"
    }

    CookieManager.getInstance().apply {
        setAcceptCookie(true)
        setAcceptThirdPartyCookies(this@configureMaengelFixWebView, false)
    }

    webChromeClient = object : WebChromeClient() {
        override fun onShowFileChooser(
            webView: WebView?,
            filePathCallback: ValueCallback<Array<Uri>>?,
            fileChooserParams: FileChooserParams?,
        ): Boolean {
            if (filePathCallback == null || fileChooserParams == null) return false
            onFileChooser(filePathCallback, fileChooserParams)
            return true
        }
    }

    webViewClient = object : WebViewClient() {
        override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
            onFatalError(null)
            onLoading(true)
        }

        override fun onPageFinished(view: WebView?, url: String?) {
            onLoading(false)
            injectGooglePlayBillingGuard(view)
        }

        override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
            if (request?.isForMainFrame == true) {
                onLoading(false)
                onFatalError(error?.description?.toString() ?: "Netzwerkfehler")
            }
        }

        override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
            val uri = request?.url ?: return null
            val blockedBillingRequest =
                uri.host.equals(BuildConfig.ALLOWED_HOST, ignoreCase = true) &&
                    request.method.equals("POST", ignoreCase = true) &&
                    (uri.path == "/api/billing/checkout" || uri.path == "/api/billing/portal")

            if (!blockedBillingRequest) return null

            val body = "{\"error\":\"Neue digitale Abos werden in der Android-App über Google Play verwaltet.\"}"
            return WebResourceResponse(
                "application/json",
                "utf-8",
                403,
                "Forbidden",
                mapOf("Cache-Control" to "no-store"),
                ByteArrayInputStream(body.toByteArray()),
            )
        }

        override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
            val uri = request?.url ?: return false

            if (uri.scheme == "maengelfix" && uri.host == "play-billing") {
                onOpenPlayBilling()
                return true
            }

            if (uri.scheme == "https" && uri.host.equals(BuildConfig.ALLOWED_HOST, ignoreCase = true)) {
                return false
            }

            val host = uri.host.orEmpty().lowercase()
            if (host == "stripe.com" || host.endsWith(".stripe.com")) {
                Toast.makeText(
                    activity,
                    "Abos werden in der Android-App über Google Play verwaltet.",
                    Toast.LENGTH_LONG,
                ).show()
                return true
            }

            return runCatching {
                activity.startActivity(Intent(Intent.ACTION_VIEW, uri))
                true
            }.getOrDefault(true)
        }
    }

    setDownloadListener(
        DownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            if (!url.startsWith("https://${BuildConfig.ALLOWED_HOST}/")) {
                Toast.makeText(activity, "Download aus unbekannter Quelle blockiert.", Toast.LENGTH_LONG).show()
                return@DownloadListener
            }

            runCatching {
                val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
                val resolvedMime = mimeType
                    ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(fileName.substringAfterLast('.', ""))
                val request = DownloadManager.Request(Uri.parse(url)).apply {
                    resolvedMime?.let(::setMimeType)
                    addRequestHeader("User-Agent", userAgent)
                    CookieManager.getInstance().getCookie(url)?.let { addRequestHeader("Cookie", it) }
                    setTitle(fileName)
                    setDescription("MängelFix Download")
                    setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
                }
                val manager = activity.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                manager.enqueue(request)
            }.onSuccess {
                Toast.makeText(activity, "Download gestartet", Toast.LENGTH_SHORT).show()
            }.onFailure {
                Toast.makeText(activity, "Download konnte nicht gestartet werden.", Toast.LENGTH_LONG).show()
            }
        }
    )
}

private fun injectGooglePlayBillingGuard(view: WebView?) {
    view?.evaluateJavascript(
        """
        (() => {
          document.documentElement.dataset.maengelFixAndroid = 'true';
          if (!location.pathname.startsWith('/app')) return;
          const styleId = 'mf-android-play-policy';
          if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
              .billingPage .primaryButton,.billingPage .secondaryButton{display:none!important}
              .mfPlayButton{display:inline-flex;align-items:center;justify-content:center;width:100%;min-height:48px;padding:12px 16px;margin-top:12px;border:0;border-radius:12px;background:#1769E0;color:#fff;font:inherit;font-weight:700;text-decoration:none}
              @media (max-width:900px){
                .workspaceShell{display:block!important;min-height:100dvh!important}
                .workspaceSidebar{position:sticky!important;top:0!important;z-index:60!important;width:100%!important;max-width:none!important;height:auto!important;min-height:0!important;padding:8px 10px!important;overflow:visible!important}
                .workspaceSidebar .sidebarBrand,.workspaceSidebar .sidebarLabel,.workspaceSidebar .sidebarBottom{display:none!important}
                .workspaceSidebar nav{display:flex!important;gap:6px!important;overflow-x:auto!important;padding:0!important;scrollbar-width:none!important}
                .workspaceSidebar nav::-webkit-scrollbar{display:none!important}
                .workspaceSidebar nav button{flex:0 0 auto!important;width:auto!important;min-width:max-content!important;min-height:44px!important;padding:9px 13px!important;border-radius:12px!important;white-space:nowrap!important}
                .workspaceSidebar nav button>span{display:none!important}
                .workspaceMain{width:100%!important;min-width:0!important;margin:0!important;padding:0!important}
                .mobileWorkspaceBar{position:sticky!important;top:60px!important;z-index:50!important;display:flex!important;padding:10px 14px!important}
                .workspacePage{padding-left:16px!important;padding-right:16px!important}
                .workspaceHeading{display:flex!important;flex-direction:column!important;align-items:flex-start!important;gap:14px!important}
                .workspaceHeading .workspacePrimary{width:100%!important;min-height:50px!important}
                .modalBackdrop{position:fixed!important;inset:0!important;z-index:9999!important;display:flex!important;align-items:flex-end!important;justify-content:center!important;padding:0!important;overflow:hidden!important;background:rgba(10,18,28,.62)!important}
                .modal.proModal{display:block!important;width:100%!important;max-width:none!important;height:auto!important;max-height:94dvh!important;margin:0!important;padding:0!important;border-radius:24px 24px 0 0!important;overflow-y:auto!important;overscroll-behavior:contain!important;background:#fff!important}
                .modal.proModal .modalHeader{position:sticky!important;top:0!important;z-index:4!important;padding:18px!important;background:#fff!important;border-bottom:1px solid #e5e9ef!important}
                .modal.proModal .caseForm{display:block!important;padding:18px 18px calc(28px + env(safe-area-inset-bottom))!important;overflow:visible!important}
                .modal.proModal .formGrid.two{display:grid!important;grid-template-columns:1fr!important;gap:14px!important}
                .modal.proModal label{display:block!important;width:100%!important;margin-bottom:14px!important}
                .modal.proModal input,.modal.proModal select,.modal.proModal textarea{width:100%!important;min-height:48px!important;box-sizing:border-box!important;font-size:16px!important}
                .modal.proModal textarea{min-height:120px!important}
                .modal.proModal .modalActions{position:sticky!important;bottom:0!important;display:grid!important;grid-template-columns:1fr!important;gap:8px!important;padding-top:12px!important;background:#fff!important}
                .modal.proModal .modalActions button{width:100%!important;min-height:50px!important}
              }`;
            document.head.appendChild(style);
          }
          const page = document.querySelector('.billingPage');
          if (page && !document.getElementById('mf-android-billing-note')) {
            const note = document.createElement('div');
            note.id = 'mf-android-billing-note';
            note.className = 'infoBox';
            note.innerHTML = '<strong>Google Play</strong><br>In der Android-App werden neue digitale Abos ausschließlich über Google Play angeboten. Dein bestehender Tarif und deine vorhandenen Funktionen bleiben nutzbar.<br><a class="mfPlayButton" href="maengelfix://play-billing">Google-Play-Abos öffnen</a>';
            page.prepend(note);
          }
        })();
        """.trimIndent(),
        null,
    )
}
