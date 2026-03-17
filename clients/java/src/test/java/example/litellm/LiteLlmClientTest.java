package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.Authenticator;
import java.net.InetSocketAddress;
import java.net.ProxySelector;
import java.net.URI;
import java.net.CookieHandler;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.time.Duration;
import java.util.Optional;
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSession;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class LiteLlmClientTest {

    private HttpServer server;
    private String baseUrl;

    @BeforeEach
    void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void sendsExpectedRequestAndParsesAssistantText() throws Exception {
        AtomicReference<String> authHeader = new AtomicReference<>();
        AtomicReference<String> requestBody = new AtomicReference<>();

        server.createContext("/v1/chat/completions", exchange -> {
            authHeader.set(exchange.getRequestHeaders().getFirst("Authorization"));
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, """
                    {"choices":[{"message":{"role":"assistant","content":"hello from java"}}]}
                    """);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-java", "o3-deep-research");
        String result = client.createChatCompletion("Hello");

        assertEquals("hello from java", result);
        assertEquals("Bearer sk-java", authHeader.get());
        assertEquals(true, requestBody.get().contains("o3-deep-research"));
    }

    @Test
    void surfacesErrorResponses() {
        server.createContext("/v1/chat/completions", exchange -> writeJson(exchange, 400, """
                {"error":{"message":"bad request"}}
                """));

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-java", "o3-deep-research");

        ApiException error = assertThrows(ApiException.class, () -> client.createChatCompletion("Hello"));
        assertEquals(400, error.statusCode());
        assertEquals(true, error.getMessage().contains("bad request"));
    }

    @Test
    void sendsResponsesApiRequestAndParsesText() throws Exception {
        AtomicReference<String> authHeader = new AtomicReference<>();
        AtomicReference<String> requestBody = new AtomicReference<>();

        server.createContext("/v1/responses", exchange -> {
            authHeader.set(exchange.getRequestHeaders().getFirst("Authorization"));
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, """
                    {"output":[{"content":[{"type":"output_text","text":{"value":"hello from responses"}}]}]}
                    """);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-java", "o3-deep-research");
        String result = client.createResponse("Hello via responses");

        assertEquals("hello from responses", result);
        assertEquals("Bearer sk-java", authHeader.get());
        assertEquals(true, requestBody.get().contains("\"input\":\"Hello via responses\""));
    }

    @Test
    void ioExceptionDoesNotInterruptCallingThread() {
        AtomicBoolean called = new AtomicBoolean(false);
        HttpClientStub stub = new HttpClientStub(() -> {
            called.set(true);
            throw new IOException("boom");
        });

        LiteLlmClient client = new LiteLlmClient(
                LiteLlmClient.normalizeBaseUrl("http://127.0.0.1:8080"),
                "sk-java",
                "o3-deep-research",
                stub);

        Thread.interrupted();
        ApiException error = assertThrows(ApiException.class, () -> client.createChatCompletion("Hello"));

        assertEquals(true, called.get());
        assertEquals(-1, error.statusCode());
        assertEquals(false, Thread.currentThread().isInterrupted());
    }

    private static void writeJson(HttpExchange exchange, int status, String payload) throws IOException {
        byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }

    private static final class HttpClientStub extends java.net.http.HttpClient {
        private final ThrowingSend send;

        private HttpClientStub(ThrowingSend send) {
            this.send = send;
        }

        @Override
        public <T> java.net.http.HttpResponse<T> send(
                java.net.http.HttpRequest request,
                java.net.http.HttpResponse.BodyHandler<T> responseBodyHandler)
                throws IOException {
            send.run();
            throw new IOException("unreachable");
        }

        @Override
        public <T> java.util.concurrent.CompletableFuture<java.net.http.HttpResponse<T>> sendAsync(
                java.net.http.HttpRequest request,
                java.net.http.HttpResponse.BodyHandler<T> responseBodyHandler) {
            throw new UnsupportedOperationException();
        }

        @Override
        public <T> java.util.concurrent.CompletableFuture<java.net.http.HttpResponse<T>> sendAsync(
                java.net.http.HttpRequest request,
                java.net.http.HttpResponse.BodyHandler<T> responseBodyHandler,
                java.net.http.HttpResponse.PushPromiseHandler<T> pushPromiseHandler) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Optional<CookieHandler> cookieHandler() {
            return Optional.empty();
        }

        @Override
        public Optional<Duration> connectTimeout() {
            return Optional.empty();
        }

        @Override
        public Redirect followRedirects() {
            return Redirect.NEVER;
        }

        @Override
        public Optional<ProxySelector> proxy() {
            return Optional.empty();
        }

        @Override
        public SSLContext sslContext() {
            try {
                SSLContext context = SSLContext.getInstance("TLS");
                context.init(null, new TrustManager[] {new NoopTrustManager()}, new SecureRandom());
                return context;
            } catch (Exception exception) {
                throw new RuntimeException(exception);
            }
        }

        @Override
        public SSLParameters sslParameters() {
            return new SSLParameters();
        }

        @Override
        public Optional<Authenticator> authenticator() {
            return Optional.empty();
        }

        @Override
        public Version version() {
            return Version.HTTP_1_1;
        }

        @Override
        public Optional<Executor> executor() {
            return Optional.empty();
        }
    }

    @FunctionalInterface
    private interface ThrowingSend {
        void run() throws IOException;
    }

    private static final class NoopTrustManager implements X509TrustManager {
        @Override
        public void checkClientTrusted(X509Certificate[] chain, String authType) {}

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String authType) {}

        @Override
        public X509Certificate[] getAcceptedIssuers() {
            return new X509Certificate[0];
        }
    }
}
