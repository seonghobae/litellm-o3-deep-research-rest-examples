package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class RelayClientTest {

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
    void posts_tool_invocation_request_to_relay() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>();

        server.createContext("/api/v1/tool-invocations", exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            writeJson(exchange, 200, """
                    {"invocation_id":"inv_123","mode":"foreground","status":"completed","deliverable_format":"markdown_brief","output_text":"relay completed"}
                    """);
        });

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.invokeDeepResearch("Explain relay mode", "markdown_brief", false, false);

        assertEquals("relay completed", result);
        assertEquals(true, requestBody.get().contains("\"tool_name\":\"deep_research\""));
        assertEquals(true, requestBody.get().contains("\"research_question\":\"Explain relay mode\""));
    }

    @Test
    void reads_completed_text_from_relay_wait_endpoint() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> writeJson(exchange, 202, """
                {"invocation_id":"inv_wait_123","mode":"background","status":"queued","deliverable_format":"markdown_brief","upstream_response_id":"resp_queued_1"}
                """));
        server.createContext("/api/v1/tool-invocations/inv_wait_123/wait", exchange -> writeJson(exchange, 200, """
                {"invocation_id":"inv_wait_123","mode":"background","status":"completed","deliverable_format":"markdown_brief","output_text":"relay waited result"}
                """));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String queued = client.invokeDeepResearch("Queue relay mode", "markdown_brief", true, false);
        String waited = client.waitForInvocation("inv_wait_123");

        assertEquals(true, queued.contains("\"invocation_id\":\"inv_wait_123\""));
        assertEquals("relay waited result", waited);
    }

    @Test
    void streams_text_from_relay_events_endpoint() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> writeJson(exchange, 202, """
                {"invocation_id":"inv_stream_123","mode":"stream","status":"pending","deliverable_format":"markdown_brief"}
                """));
        server.createContext("/api/v1/tool-invocations/inv_stream_123/events", exchange -> writeText(exchange, 200, "text/event-stream", """
                event: status
                data: {"invocation_id":"inv_stream_123","type":"status","status":"pending","data":{"mode":"stream"}}

                event: output_text
                data: {"invocation_id":"inv_stream_123","type":"output_text","status":"running","data":{"text":"Hello"}}

                event: output_text
                data: {"invocation_id":"inv_stream_123","type":"output_text","status":"running","data":{"text":" world"}}

                event: completed
                data: {"invocation_id":"inv_stream_123","type":"completed","status":"completed","data":{"output_text":"Hello world"}}

                """));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String streamed = client.invokeDeepResearch("Stream relay mode", "markdown_brief", false, true);

        assertEquals("Hello world", streamed);
    }

    private static void writeJson(HttpExchange exchange, int status, String payload) throws IOException {
        writeText(exchange, status, "application/json", payload);
    }

    private static void writeText(HttpExchange exchange, int status, String contentType, String payload)
            throws IOException {
        byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", contentType);
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }
}
