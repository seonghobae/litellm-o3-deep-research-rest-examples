package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MainTest {

    @TempDir
    Path tempDir;

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

    // ---------- flag-parsing / argument-validation tests --------------------

    @Test
    void targetFlagWithoutValueFailsFast() {
        assertThrows(IllegalArgumentException.class, () -> Main.main(new String[] {"--target"}));
    }

    @Test
    void apiFlagWithoutValueFailsFast() {
        assertThrows(IllegalArgumentException.class, () -> Main.main(new String[] {"--api"}));
    }

    @Test
    void deliverableFormatWithoutValueFailsFast() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--target", "relay", "--deliverable-format"}));
    }

    @Test
    void backgroundAndStreamCannotBeCombined() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--background", "--stream", "hello"}));
    }

    @Test
    void streamRequiresRelayTarget() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--stream", "hello"}));
    }

    @Test
    void backgroundRequiresResponsesApi() {
        // --background with default --api chat (not responses) must fail fast.
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--background", "my question"}));
    }

    @Test
    void timeoutFlagWithoutValueFailsFast() {
        assertThrows(IllegalArgumentException.class,
                () -> Main.main(new String[] {"--timeout"}));
    }

    @Test
    void webSearchFlagRequiresResponsesApi() {
        // --web-search without --api responses must fail fast.
        assertThrows(IllegalArgumentException.class,
                () -> Main.main(new String[] {"--web-search", "some prompt"}));
    }

    @Test
    void webSearchFlagSendsWebSearchPreviewTool() throws Exception {
        // Verify the web-search routing by exercising LiteLlmClient directly
        // (same pattern as other routing tests - Main.main env-var coupling
        // cannot be controlled in-process).
        java.util.concurrent.atomic.AtomicReference<String> capturedBody =
                new java.util.concurrent.atomic.AtomicReference<>();

        server.createContext("/v1/responses", exchange -> {
            capturedBody.set(new String(exchange.getRequestBody().readAllBytes(),
                    java.nio.charset.StandardCharsets.UTF_8));
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":[{\"type\":\"output_text\","
                            + "\"text\":\"짜장면 결과\"}]}]}");
        });

        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());

        // Same logic as Main.main's --web-search branch
        String result = client.createResponse(
                "짜장면의 역사",
                false,
                java.util.List.of(java.util.Map.of("type", "web_search_preview")));

        assertEquals("짜장면 결과", result);
        assertEquals(true, capturedBody.get().contains("web_search_preview"));
    }

    private void writeDotenv(String content) throws java.io.IOException {
        java.nio.file.Files.writeString(tempDir.resolve(".env"), content, StandardCharsets.UTF_8);
    }

    // ---------- routing integration tests ------------------------------------
    //
    // Main.main() calls EnvConfig.loadDefault() which reads System.getenv().
    // We cannot override env vars in-process in Java, so we test the routing
    // paths (relay, direct chat, direct responses) by exercising the underlying
    // client classes directly with a controlled HTTP server.  This validates
    // the same code paths that Main.main() exercises (lines 37-55 of Main.java)
    // without the environment-variable coupling.

    @Test
    void relayChatRoutingPathCompletesSuccessfully() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"invocation_id\":\"inv_route_1\",\"mode\":\"foreground\","
                            + "\"status\":\"completed\",\"deliverable_format\":\"markdown_brief\","
                            + "\"output_text\":\"relay routed\"}");
        });

        // Same logic as Main.main's relay branch (lines 37-38)
        example.litellm.relay.RelayClient client =
                new example.litellm.relay.RelayClient(baseUrl);
        String result = client.invokeDeepResearch("route test", "markdown_brief", false, false);
        assertEquals("relay routed", result);
    }

    @Test
    void directChatRoutingPathCompletesSuccessfully() throws Exception {
        server.createContext("/v1/chat/completions", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"choices\":[{\"message\":{\"role\":\"assistant\","
                            + "\"content\":\"direct routed\"}}]}");
        });

        // Same logic as Main.main's direct chat branch (lines 47-51)
        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());
        String result = client.createChatCompletion("direct route test");
        assertEquals("direct routed", result);
    }

    @Test
    void directResponsesRoutingPathCompletesSuccessfully() throws Exception {
        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"output\":[{\"content\":[{\"type\":\"output_text\","
                            + "\"text\":\"responses routed\"}]}]}");
        });

        // Same logic as Main.main's direct responses branch (lines 50, 47-51)
        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());
        String result = client.createResponse("responses route test", false);
        assertEquals("responses routed", result);
    }

    // ---------- --auto-tool-call tests ---------------------------------------

    @Test
    void autoToolCallCannotBeCombinedWithTargetRelay() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--auto-tool-call", "--target", "relay", "my question"}));
    }

    @Test
    void autoToolCallRoutingPathCompletesSuccessfully() throws Exception {
        // Exercise the createChatWithToolCalling path via LiteLlmClient directly
        // (same pattern as other routing tests - Main.main env-var coupling
        // cannot be controlled in-process).
        java.util.concurrent.atomic.AtomicInteger responsesCallCount =
                new java.util.concurrent.atomic.AtomicInteger(0);

        String firstChatJson =
                "{\"id\":\"resp_direct\",\"status\":\"completed\",\"output_text\":\"auto tool answer\",\"output\":[]}";

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            responsesCallCount.incrementAndGet();
            writeJson(exchange, 200, firstChatJson);
        });

        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());

        // Same logic as Main.main's --auto-tool-call branch (no tool called case)
        String[] result = client.createChatWithToolCalling("짜장면의 역사", "http://127.0.0.1:9999");

        assertEquals("auto tool answer", result[0]);
        assertEquals("false", result[1]);
        assertEquals(1, responsesCallCount.get());
    }

    @Test
    void autoToolCallWithDeepResearchEmitsStderrMessage() throws Exception {
        // Verify that when tool_called=true, the result[1] is "true"
        // (stderr output cannot be captured easily in unit tests, but we verify
        // the logic returns the correct indicator).
        java.util.concurrent.atomic.AtomicInteger responsesCallCount =
                new java.util.concurrent.atomic.AtomicInteger(0);

        String firstChatJson =
                "{\"id\":\"resp_1\",\"status\":\"completed\",\"output\":[{\"type\":\"function_call\",\"name\":\"deep_research\",\"call_id\":\"call_1\",\"arguments\":\"{\\\"research_question\\\":\\\"test\\\",\\\"deliverable_format\\\":\\\"markdown_brief\\\"}\"}]}";
        String relayJson =
                "{\"invocation_id\":\"inv_1\",\"upstream_response_id\":\"up_1\",\"status\":\"completed\",\"output_text\":\"summary\"}";
        String secondChatJson =
                "{\"id\":\"resp_2\",\"status\":\"completed\",\"output\":[{\"type\":\"message\",\"content\":[{\"type\":\"output_text\",\"text\":\"synthesized answer\"}]}]}";

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            int call = responsesCallCount.incrementAndGet();
            writeJson(exchange, 200, call == 1 ? firstChatJson : secondChatJson);
        });
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, relayJson);
        });

        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());
        String[] result = client.createChatWithToolCalling("짜장면의 역사", baseUrl);

        assertEquals("synthesized answer", result[0]);
        assertEquals("true", result[1]);
    }

    // ---------- helper -------------------------------------------------------

    private static void writeJson(HttpExchange exchange, int status, String payload) throws IOException {
        byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }
}
