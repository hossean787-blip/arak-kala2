package ir.arakkala.shop;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Collections;

public final class MainActivity extends Activity {
    private static final int CHOOSE_FILE = 1;
    private static final int SAVE_DOWNLOAD = 2;

    private StoreEndpoint endpoint;
    private FrameLayout browser;
    private View status;
    private ProgressBar progress;
    private WebView webView;
    private ValueCallback<Uri[]> fileResult;
    private String pendingDownload;
    private Api33Back backHandler;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        browser = findViewById(R.id.browser);
        status = findViewById(R.id.status);
        progress = findViewById(R.id.progress);
        applyInsets(findViewById(R.id.root));

        endpoint = StoreEndpoint.from(getString(R.string.store_url));
        if (endpoint == null) {
            return;
        }

        findViewById(R.id.retry).setOnClickListener(view -> loadStore());
        webView = new WebView(this);
        browser.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        configureBrowser();
        if (Build.VERSION.SDK_INT >= 33) {
            backHandler = new Api33Back(getOnBackInvokedDispatcher(), this::navigateBack);
        }

        if (savedInstanceState != null) {
            pendingDownload = savedInstanceState.getString("pendingDownload");
            Bundle history = savedInstanceState.getBundle("browserHistory");
            if (history != null && webView.restoreState(history) != null) {
                showBrowser();
                return;
            }
        }
        loadStore();
    }

    private void applyInsets(View root) {
        if (Build.VERSION.SDK_INT < 30) {
            return;
        }
        getWindow().setDecorFitsSystemWindows(false);
        WindowInsetsController controller = getWindow().getInsetsController();
        if (controller != null) {
            int appearance = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                    | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
            controller.setSystemBarsAppearance(appearance, appearance);
        }
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            int types = WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
                    | WindowInsets.Type.ime();
            android.graphics.Insets padding = insets.getInsets(types);
            view.setPadding(padding.left, padding.top, padding.right, padding.bottom);
            return WindowInsets.CONSUMED;
        });
        root.requestApplyInsets();
    }

    private void configureBrowser() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !endpoint.allows(request.getUrl().toString());
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (endpoint.allows(request.getUrl().toString())) {
                    return null;
                }
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
                        Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (!endpoint.allows(url)) {
                    view.stopLoading();
                    showConnectionError();
                }
            }

            @Override
            public void onReceivedError(
                    WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    showConnectionError();
                }
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value < 100 && browser.isShown() ? View.VISIBLE : View.GONE);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> result,
                    FileChooserParams parameters) {
                if (view.getUrl() == null || !endpoint.allows(view.getUrl())) {
                    result.onReceiveValue(null);
                    return true;
                }
                if (fileResult != null) {
                    fileResult.onReceiveValue(null);
                }
                fileResult = result;
                try {
                    startActivityForResult(parameters.createIntent(), CHOOSE_FILE);
                } catch (ActivityNotFoundException exception) {
                    fileResult = null;
                    result.onReceiveValue(null);
                    Toast.makeText(MainActivity.this, R.string.choose_file_failed, Toast.LENGTH_SHORT).show();
                }
                return true;
            }
        });
        webView.setDownloadListener((url, userAgent, disposition, mimeType, length) ->
                chooseDownloadDestination(url, disposition, mimeType));
    }

    private void loadStore() {
        showBrowser();
        webView.loadUrl(endpoint.homeUrl());
    }

    private void showBrowser() {
        status.setVisibility(View.GONE);
        browser.setVisibility(View.VISIBLE);
    }

    private void showConnectionError() {
        browser.setVisibility(View.GONE);
        progress.setVisibility(View.GONE);
        TextView title = findViewById(R.id.status_title);
        TextView description = findViewById(R.id.status_description);
        title.setText(R.string.connection_title);
        description.setText(R.string.connection_description);
        findViewById(R.id.retry).setVisibility(View.VISIBLE);
        status.setVisibility(View.VISIBLE);
    }

    private void chooseDownloadDestination(String url, String disposition, String mimeType) {
        if (!endpoint.allows(url) || pendingDownload != null) {
            return;
        }
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType(mimeType == null || mimeType.isEmpty() ? "application/octet-stream" : mimeType)
                .putExtra(Intent.EXTRA_TITLE, URLUtil.guessFileName(url, disposition, mimeType));
        try {
            pendingDownload = url;
            startActivityForResult(intent, SAVE_DOWNLOAD);
        } catch (ActivityNotFoundException exception) {
            pendingDownload = null;
            Toast.makeText(this, R.string.save_file_failed, Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == CHOOSE_FILE && fileResult != null) {
            ValueCallback<Uri[]> callback = fileResult;
            fileResult = null;
            Uri[] files = WebChromeClient.FileChooserParams.parseResult(result, data);
            if (files != null) {
                for (Uri file : files) {
                    if (file == null || !"content".equals(file.getScheme())) {
                        callback.onReceiveValue(null);
                        return;
                    }
                }
            }
            callback.onReceiveValue(files);
        } else if (request == SAVE_DOWNLOAD) {
            String url = pendingDownload;
            pendingDownload = null;
            if (endpoint != null && url != null && endpoint.allows(url) && result == RESULT_OK
                    && data != null && data.getData() != null
                    && "content".equals(data.getData().getScheme())) {
                Uri destination = data.getData();
                String userAgent = webView.getSettings().getUserAgentString();
                new Thread(() -> saveDownload(url, destination, userAgent), "arak-kala-download").start();
            }
        }
    }

    private void saveDownload(String url, Uri destination, String userAgent) {
        HttpURLConnection connection = null;
        int message = R.string.save_file_failed;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(30000);
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null) {
                connection.setRequestProperty("Cookie", cookie);
            }
            connection.setRequestProperty("User-Agent", userAgent);

            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new IOException("Unexpected response: " + code);
            }
            try (InputStream input = connection.getInputStream();
                    OutputStream output = getContentResolver().openOutputStream(destination, "w")) {
                if (output == null) {
                    throw new IOException("The document provider returned no output stream");
                }
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                }
            }
            message = R.string.save_file_success;
        } catch (IOException | SecurityException exception) {
            try {
                DocumentsContract.deleteDocument(getContentResolver(), destination);
            } catch (IOException | RuntimeException ignored) {
                // A provider may decline cleanup of the newly created document.
            }
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
        int resultText = message;
        runOnUiThread(() -> Toast.makeText(this, resultText, Toast.LENGTH_SHORT).show());
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        if (webView != null) {
            Bundle history = new Bundle();
            webView.saveState(history);
            state.putBundle("browserHistory", history);
        }
        state.putString("pendingDownload", pendingDownload);
    }

    @Override
    public void onBackPressed() {
        navigateBack();
    }

    private void navigateBack() {
        if (webView != null && browser.isShown() && webView.canGoBack()) {
            webView.goBack();
        } else {
            finish();
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
        }
    }

    @Override
    protected void onDestroy() {
        if (backHandler != null) {
            backHandler.unregister();
        }
        if (fileResult != null) {
            fileResult.onReceiveValue(null);
            fileResult = null;
        }
        if (webView != null) {
            browser.removeView(webView);
            webView.destroy();
        }
        super.onDestroy();
    }

    private static final class Api33Back {
        private final OnBackInvokedDispatcher dispatcher;
        private final OnBackInvokedCallback callback;

        Api33Back(OnBackInvokedDispatcher dispatcher, Runnable handler) {
            this.dispatcher = dispatcher;
            callback = handler::run;
            dispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, callback);
        }

        void unregister() {
            dispatcher.unregisterOnBackInvokedCallback(callback);
        }
    }
}
