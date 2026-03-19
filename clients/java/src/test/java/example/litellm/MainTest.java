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
