package local.baiduoffline;

import java.io.IOException;
import java.net.Proxy;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLStreamHandler;

/** Fail HTTP requests through the normal IOException path before DNS or sockets. */
public final class OfflineNetwork {
    private static boolean installed;

    public static synchronized void install() {
        if (installed) return;
        URL.setURLStreamHandlerFactory(protocol -> {
            if (!"http".equals(protocol) && !"https".equals(protocol)) return null;
            return new URLStreamHandler() {
                @Override protected URLConnection openConnection(URL url) throws IOException {
                    throw new IOException("Network disabled in offline build");
                }
                @Override protected URLConnection openConnection(URL url, Proxy proxy) throws IOException {
                    throw new IOException("Network disabled in offline build");
                }
            };
        });
        installed = true;
    }
}
