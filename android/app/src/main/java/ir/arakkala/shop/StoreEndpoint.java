package ir.arakkala.shop;

import java.net.URI;
import java.net.URISyntaxException;

final class StoreEndpoint {
    private final URI home;

    private StoreEndpoint(URI home) {
        this.home = home;
    }

    static StoreEndpoint from(String url) {
        URI home = parseHttps(url);
        return home == null ? null : new StoreEndpoint(home);
    }

    String homeUrl() {
        return home.toASCIIString();
    }

    boolean allows(String url) {
        URI candidate = parseHttps(url);
        return candidate != null
                && home.getHost().equalsIgnoreCase(candidate.getHost())
                && effectivePort(home) == effectivePort(candidate);
    }

    private static URI parseHttps(String value) {
        if (value == null) {
            return null;
        }
        try {
            URI uri = new URI(value.trim());
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getRawUserInfo() != null || uri.getPort() == 0
                    || uri.getPort() > 65535) {
                return null;
            }
            return uri;
        } catch (URISyntaxException exception) {
            return null;
        }
    }

    private static int effectivePort(URI uri) {
        return uri.getPort() == -1 ? 443 : uri.getPort();
    }
}
