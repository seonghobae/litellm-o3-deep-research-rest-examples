package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertNull;

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
import java.util.List;
import java.util.Optional;
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
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
    void sendsBackgroundResponsesRequestAndReturnsRawMetadata() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>();

        server.createContext("/v1/responses", exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, """
                    {"id":"resp_background_123","object":"response","status":"queued","background":true}
                    """);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-java", "o3-deep-research");
        String result = client.createResponse("Hello via background responses", true);

        assertEquals(true, requestBody.get().contains("\"background\":true"));
        assertEquals(true, result.contains("\"id\":\"resp_background_123\""));
        assertEquals(true, result.contains("\"status\":\"queued\""));
    }

    @Test
    void sendsResponsesApiRequestAndParsesTopLevelOutputText() throws Exception {
        // H-8: cover the early-return path in extractResponseText() for a
        // top-level "output_text" string (most concise Responses API shape).
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes(); // drain
            writeJson(exchange, 200,
                    "{\"id\":\"resp_top_1\",\"object\":\"response\",\"status\":\"completed\",\"output_text\":\"top-level answer\"}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String text = client.createResponse("top-level output question", false);

        assertEquals("top-level answer", text);
    }

    // ---- normalizeBaseUrl: URISyntaxException path ---------------------------

    @Test
    void normalizeBaseUrlRejectsHardlyValidUri() {
        // Force the URISyntaxException catch path by supplying a URI string that
        // parses but has no scheme/host component so we take the IAE branch.
        assertThrows(IllegalArgumentException.class,
                () -> LiteLlmClient.normalizeBaseUrl("not a uri at all :// ??? "));
    }

    // ---- invalid JSON response -----------------------------------------------

    @Test
    void raisesApiExceptionWhenResponseBodyIsNotJson() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            byte[] body = "not valid json".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "text/plain");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream out = exchange.getResponseBody()) { out.write(body); }
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("bad json"));
        assertEquals(true, ex.getMessage().contains("invalid JSON"));
    }

    // ---- extractErrorMessage: non-JSON body fallback -------------------------

    @Test
    void surfacesGenericMessageWhenErrorBodyIsNotJson() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 500, "not json at all");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("trigger 500"));
        assertEquals(500, ex.statusCode());
        // generic fallback message when JSON parse fails
        assertEquals(true, ex.getMessage().toLowerCase().contains("error"));
    }

    @Test
    void surfacesGenericMessageWhenErrorObjectHasNoMessageKey() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 503, "{\"error\":{\"code\":503}}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("trigger 503"));
        assertEquals(503, ex.statusCode());
        assertEquals(true, ex.getMessage().toLowerCase().contains("error"));
    }

    // ---- extractAssistantText: no choices / list-of-blocks / final raise ----

    @Test
    void raisesApiExceptionWhenResponseHasNoChoices() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, "{\"choices\":[]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("no choices"));
        assertEquals(true, ex.getMessage().contains("choices"));
    }

    @Test
    void parsesListOfContentBlocksFromChatCompletion() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"block-\"},{\"type\":\"text\",\"text\":\"reply\"}]}}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createChatCompletion("block content");
        assertEquals("block-reply", result);
    }

    @Test
    void raisesApiExceptionWhenNoUsableAssistantMessage() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"\"}}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("empty content"));
        assertEquals(true, ex.getMessage().toLowerCase().contains("usable"));
    }

    // ---- extractResponseText: edge cases ------------------------------------

    @Test
    void raisesApiExceptionWhenResponseHasNoOutputItems() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, "{\"output\":[]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createResponse("no output"));
        assertEquals(true, ex.getMessage().toLowerCase().contains("output"));
    }

    @Test
    void skipsOutputItemsWithNonArrayContent() throws Exception {
        // content is not an array → skip; second item has valid content → use it
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":\"not an array\"},{\"content\":[{\"type\":\"output_text\",\"text\":\"good\"}]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createResponse("non-array content");
        assertEquals("good", result);
    }

    @Test
    void skipsBlocksWithUnrecognisedTypeInOutputArray() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":[{\"type\":\"reasoning\",\"text\":\"skip\"},{\"type\":\"output_text\",\"text\":\"keep\"}]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createResponse("skip reasoning type");
        assertEquals("keep", result);
    }

    @Test
    void skipsBlocksWithNullTextField() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":[{\"type\":\"output_text\"},{\"type\":\"output_text\",\"text\":\"real\"}]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createResponse("null text field");
        assertEquals("real", result);
    }

    @Test
    void collectsPlainStringTextField() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":[{\"type\":\"output_text\",\"text\":\"plain string\"}]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createResponse("plain text field");
        assertEquals("plain string", result);
    }

    @Test
    void raisesApiExceptionWhenAllBlocksAreSkipped() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":[{\"type\":\"reasoning\",\"text\":\"skip me\"}]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createResponse("all skipped"));
        assertEquals(true, ex.getMessage().toLowerCase().contains("usable"));
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

    // ---- custom timeout constructor ------------------------------------------

    @Test
    void customTimeoutConstructorIsUsedForRequests() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"timeout path\"}}]}");
        });

        // Use the public Duration constructor to verify it wires through correctly.
        LiteLlmClient client = new LiteLlmClient(
                baseUrl, "sk-test", "o3-deep-research",
                java.time.Duration.ofSeconds(120));
        String result = client.createChatCompletion("custom timeout question");
        assertEquals("timeout path", result);
    }

    // ---- web_search_preview tools support -----------------------------------

    @Test
    void sendsWebSearchToolInRequestBodyWhenProvided() throws Exception {
        java.util.concurrent.atomic.AtomicReference<String> capturedBody =
                new java.util.concurrent.atomic.AtomicReference<>();

        server.createContext("/v1/responses", exchange -> {
            capturedBody.set(new String(exchange.getRequestBody().readAllBytes(),
                    java.nio.charset.StandardCharsets.UTF_8));
            writeJson(exchange, 200,
                    "{\"output_text\":\"web search result\"}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "gpt-4o");
        String result = client.createResponse(
                "짜장면의 역사",
                false,
                java.util.List.of(java.util.Map.of("type", "web_search_preview")));

        assertEquals("web search result", result);
        assertEquals(true, capturedBody.get().contains("web_search_preview"));
        assertEquals(true, capturedBody.get().contains("\"tools\""));
    }

    @Test
    void omitsToolsFieldWhenNullProvided() throws Exception {
        java.util.concurrent.atomic.AtomicReference<String> capturedBody =
                new java.util.concurrent.atomic.AtomicReference<>();

        server.createContext("/v1/responses", exchange -> {
            capturedBody.set(new String(exchange.getRequestBody().readAllBytes(),
                    java.nio.charset.StandardCharsets.UTF_8));
            writeJson(exchange, 200, "{\"output_text\":\"no tools result\"}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "gpt-4o");
        client.createResponse("Hello", false, null);

        assertEquals(false, capturedBody.get().contains("\"tools\""));
    }

    // ---- extractResponseText: blank top-level output_text falls through --------

    @Test
    void fallsThroughWhenTopLevelOutputTextIsBlank() throws Exception {
        // outputText.isBlank() → falls through to output[] traversal
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output_text\":\"   \","
                            + "\"output\":[{\"content\":[{\"type\":\"output_text\",\"text\":\"fallback\"}]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createResponse("blank top-level");
        assertEquals("fallback", result);
    }

    @Test
    void skipsBlocksWithObjectTextAndNullValue() throws Exception {
        // text.isObject() but value == null → skip; next block is valid
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":["
                            + "{\"type\":\"output_text\",\"text\":{\"value\":null}},"
                            + "{\"type\":\"output_text\",\"text\":\"real\"}"
                            + "]}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        String result = client.createResponse("null object value");
        assertEquals("real", result);
    }

    @Test
    void extractErrorMessageFallsBackWhenErrorFieldIsNotObject() throws Exception {
        // error field exists but is a string, not an object → fallback generic
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 400, "{\"error\":\"just a string\"}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("string error field"));
        assertEquals(400, ex.statusCode());
        assertEquals(true, ex.getMessage().toLowerCase().contains("error"));
    }

    @Test
    void extractAssistantTextRaisesWhenListOfBlocksIsEmpty() throws Exception {
        // content.isArray() but no blocks with text → raises usable message error
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":[]}}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("empty array content"));
        assertEquals(true, ex.getMessage().toLowerCase().contains("usable"));
    }

    @Test
    void extractAssistantTextRaisesWhenBlocksHaveNoTextField() throws Exception {
        // content.isArray() with blocks but no "text" key → raises
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"choices\":[{\"message\":{\"role\":\"assistant\","
                            + "\"content\":[{\"type\":\"image_url\",\"image_url\":\"http://img.example\"}]}}]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "sk-test", "o3-deep-research");
        ApiException ex = assertThrows(ApiException.class,
                () -> client.createChatCompletion("no text in blocks"));
        assertEquals(true, ex.getMessage().toLowerCase().contains("usable"));
    }

    // ---- createChatWithToolCalling tests ------------------------------------

    @Test
    void createChatWithToolCalling_no_tool_call_returns_direct_answer() throws Exception {
        String firstJson = """
                {"id":"resp_1","output_text":"Direct answer.","output":[]}
                """;
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, firstJson);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "key", "gpt-4o");
        String[] result = client.createChatWithToolCalling("Hello", "http://127.0.0.1:9999");
        assertEquals("Direct answer.", result[0]);
        assertEquals("false", result[1]);
    }

    @Test
    void createChatWithToolCalling_with_tool_call_executes_research() throws Exception {
        AtomicInteger responseCallCount = new AtomicInteger(0);
        AtomicReference<String> relayBody = new AtomicReference<>("");

        String firstResponseJson =
                "{\"id\":\"resp_1\",\"output\":[{\"type\":\"function_call\",\"name\":\"deep_research\",\"call_id\":\"call_1\","
                + "\"arguments\":\"{\\\"research_question\\\":\\\"test q\\\",\\\"deliverable_format\\\":\\\"markdown_brief\\\"}\"}]}";
        String secondResponseJson = """
                {"id":"resp_2","output_text":"Final answer.","output":[]}
                """;
        String relayJson = """
                {"output_text":"summary text","status":"completed","mode":"foreground"}
                """;

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            int call = responseCallCount.incrementAndGet();
            writeJson(exchange, 200, call == 1 ? firstResponseJson : secondResponseJson);
        });
        server.createContext("/api/v1/tool-invocations", exchange -> {
            relayBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, relayJson);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "key", "gpt-4o");
        String[] result = client.createChatWithToolCalling("짜장면 역사", baseUrl);
        assertEquals("Final answer.", result[0]);
        assertEquals("true", result[1]);
        assertEquals(true, relayBody.get().contains("\"tool_name\":\"deep_research\""));
    }

    @Test
    void createChatWithToolCalling_no_choices_throws() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, "{\"output\":[]}");
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "key", "gpt-4o");
        assertThrows(ApiException.class, () -> client.createChatWithToolCalling("Hello", "http://127.0.0.1:9999"));
    }

    @Test
    void createChatWithToolCalling_second_turn_no_choices_returns_summary() throws Exception {
        AtomicInteger responseCallCount = new AtomicInteger(0);

        String firstResponseJson =
                "{\"id\":\"resp_1\",\"output\":[{\"type\":\"function_call\",\"name\":\"deep_research\",\"call_id\":\"call_1\","
                + "\"arguments\":\"{\\\"research_question\\\":\\\"q\\\",\\\"deliverable_format\\\":\\\"markdown_brief\\\"}\"}]}";
        String secondResponseJson = """
                {"id":"resp_2","output":[]}
                """;
        String relayJson = """
                {"output_text":"summary fallback"}
                """;

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            int call = responseCallCount.incrementAndGet();
            writeJson(exchange, 200, call == 1 ? firstResponseJson : secondResponseJson);
        });
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, relayJson);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "key", "gpt-4o");
        String[] result = client.createChatWithToolCalling("Q", baseUrl);
        assertEquals("summary fallback", result[0]);
        assertEquals("true", result[1]);
    }

    @Test
    void createChatWithToolCalling_non_deep_research_tool_treated_as_no_call() throws Exception {
        String firstJson = """
                {"id":"resp_1","output_text":"direct","output":[{"type":"function_call","name":"other_tool","call_id":"call_x","arguments":"{}"}]}
                """;
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, firstJson);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "key", "gpt-4o");
        String[] result = client.createChatWithToolCalling("Q", "http://127.0.0.1:9999");
        assertEquals("direct", result[0]);
        assertEquals("false", result[1]);
    }

    @Test
    void createChatWithToolCalling_invalid_json_args_falls_back_to_prompt() throws Exception {
        AtomicInteger responseCallCount = new AtomicInteger(0);

        String firstResponseJson = """
                {"id":"resp_1","output":[{"type":"function_call","name":"deep_research","call_id":"call_1","arguments":"INVALID"}]}
                """;
        String secondResponseJson = """
                {"id":"resp_2","output_text":"done","output":[]}
                """;
        String relayJson = """
                {"output_text":"s"}
                """;

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            int call = responseCallCount.incrementAndGet();
            writeJson(exchange, 200, call == 1 ? firstResponseJson : secondResponseJson);
        });
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, relayJson);
        });

        LiteLlmClient client = new LiteLlmClient(baseUrl, "key", "gpt-4o");
        String[] result = client.createChatWithToolCalling("my prompt", baseUrl);
        assertEquals("done", result[0]);
        assertEquals("true", result[1]);
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
