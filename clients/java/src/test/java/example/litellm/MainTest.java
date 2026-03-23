package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.PrintStream;
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
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--background", "my question"}));
    }

    @Test
    void timeoutFlagWithoutValueFailsFast() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--timeout"}));
        assertEquals("--timeout requires a value", ex.getMessage());
    }

    @Test
    void timeoutFlagWithNonNumericValueFailsFast() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> Main.parseTimeoutSeconds("abc"));
        assertEquals("--timeout must be a positive integer number of seconds: abc", ex.getMessage());
        assertTrue(ex.getCause() instanceof NumberFormatException);
    }

    @Test
    void timeoutFlagWithZeroValueFailsFast() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> Main.parseTimeoutSeconds("0"));
        assertEquals("--timeout must be greater than 0 seconds: 0", ex.getMessage());
    }

    @Test
    void timeoutFlagWithNegativeValueFailsFast() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> Main.parseTimeoutSeconds("-5"));
        assertEquals("--timeout must be greater than 0 seconds: -5", ex.getMessage());
    }

    @Test
    void timeoutFlagWithPositiveValueParsesSeconds() {
        assertEquals(java.time.Duration.ofSeconds(30), Main.parseTimeoutSeconds("30"));
    }

    @Test
    void helpFlagPrintsUsageAndReturnsWithoutEnvOrNetwork() {
        PrintStream originalOut = System.out;
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try {
            System.setOut(new PrintStream(buffer, true, StandardCharsets.UTF_8));

            Main.main(new String[] {"--help"});

            String output = buffer.toString(StandardCharsets.UTF_8);
            assertEquals(true, output.contains("Usage: java -jar litellm-o3-deep-research-java-0.1.0.jar"));
            assertEquals(true, output.contains("--timeout <seconds>"));
            assertEquals(true, output.contains("--target relay"));
        } finally {
            System.setOut(originalOut);
        }
    }

    @Test
    void webSearchFlagRequiresResponsesApi() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--web-search", "some prompt"}));
    }

    @Test
    void webSearchFlagSendsWebSearchPreviewTool() throws Exception {
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

    @Test
    void relayChatRoutingPathCompletesSuccessfully() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200,
                    "{\"invocation_id\":\"inv_route_1\",\"mode\":\"foreground\","
                            + "\"status\":\"completed\",\"deliverable_format\":\"markdown_brief\","
                            + "\"output_text\":\"relay routed\"}");
        });

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
        java.util.concurrent.atomic.AtomicInteger responsesCallCount =
                new java.util.concurrent.atomic.AtomicInteger(0);

        String firstResponsesJson =
                "{\"id\":\"resp_direct\",\"status\":\"completed\",\"output_text\":\"auto tool answer\",\"output\":[]}";

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            responsesCallCount.incrementAndGet();
            writeJson(exchange, 200, firstResponsesJson);
        });

        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());

        LiteLlmClient.ToolCallingResult result = client.createResponseWithToolCalling(
                "짜장면의 역사", "http://127.0.0.1:9999");

        assertEquals("auto tool answer", result.finalText());
        assertEquals(false, result.toolCalled());
        assertEquals("resp_direct", result.responseId());
        assertEquals(1, responsesCallCount.get());
    }

    @Test
    void autoToolCallWithDeepResearchEmitsStderrMessage() throws Exception {
        java.util.concurrent.atomic.AtomicInteger responsesCallCount =
                new java.util.concurrent.atomic.AtomicInteger(0);
        java.util.concurrent.atomic.AtomicReference<String> relayBody =
                new java.util.concurrent.atomic.AtomicReference<>("");

        String firstResponsesJson =
                "{\"id\":\"resp_1\",\"status\":\"completed\",\"output\":[{\"type\":\"function_call\",\"name\":\"deep_research\",\"call_id\":\"call_1\",\"arguments\":\"{\\\"research_question\\\":\\\"test\\\",\\\"deliverable_format\\\":\\\"markdown_brief\\\"}\"}]}";
        String relayJson =
                "{\"invocation_id\":\"inv_1\",\"invocation_token\":\"tok_1\",\"upstream_response_id\":\"up_1\",\"status\":\"completed\",\"output_text\":\"summary\"}";
        String secondResponsesJson =
                "{\"id\":\"resp_2\",\"status\":\"completed\",\"output\":[{\"type\":\"message\",\"content\":[{\"type\":\"output_text\",\"text\":\"synthesized answer\"}]}]}";

        server.createContext("/v1/responses", exchange -> {
            exchange.getRequestBody().readAllBytes();
            int call = responsesCallCount.incrementAndGet();
            writeJson(exchange, 200, call == 1 ? firstResponsesJson : secondResponsesJson);
        });
        server.createContext("/api/v1/tool-invocations", exchange -> {
            relayBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, relayJson);
        });

        EnvConfig cfg = EnvConfig.load(
                tempDir.resolve(".env"),
                java.util.Map.of("LITELLM_BASE_URL", baseUrl, "LITELLM_API_KEY", "sk-test"));
        LiteLlmClient client = new LiteLlmClient(cfg.baseUrl(), cfg.apiKey(), cfg.model());
        LiteLlmClient.ToolCallingResult result = client.createResponseWithToolCalling(
                "짜장면의 역사", baseUrl);

        assertEquals("synthesized answer", result.finalText());
        assertEquals(true, result.toolCalled());
        assertEquals("resp_2", result.responseId());
        assertEquals("resp_1", result.previousResponseId());
        assertEquals("call_1", result.toolCallId());
        assertEquals("inv_1", result.invocationId());
        assertEquals("tok_1", result.invocationToken());
        assertEquals("up_1", result.upstreamResponseId());
        assertEquals(true, relayBody.get().contains("\"tool_name\":\"deep_research\""));
        assertEquals(true, relayBody.get().contains("\"deliverable_format\":\"markdown_brief\""));
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
