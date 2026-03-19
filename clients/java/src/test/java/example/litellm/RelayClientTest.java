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

    @Test
    void streams_text_ignores_non_output_text_sse_events() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> writeJson(exchange, 202, """
                {"invocation_id":"inv_ignore_123","mode":"stream","status":"pending","deliverable_format":"markdown_brief"}
                """));
        server.createContext("/api/v1/tool-invocations/inv_ignore_123/events", exchange -> writeText(exchange, 200, "text/event-stream", """
                event: status
                data: {"invocation_id":"inv_ignore_123","type":"status","status":"pending","data":{"mode":"stream"}}

                event: output_text
                data: {"invocation_id":"inv_ignore_123","type":"output_text","status":"running","data":{"text":"Only this"}}

                event: completed
                data: {"invocation_id":"inv_ignore_123","type":"completed","status":"completed","data":{"output_text":"Only this"}}

                """));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String streamed = client.invokeDeepResearch("Stream relay ignoring events", "markdown_brief", false, true);

        // status and completed events have no "text" field; only the output_text event contributes text.
        assertEquals("Only this", streamed);
    }

    @Test
    void streams_text_raises_api_exception_on_malformed_json_sse_frame() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> writeJson(exchange, 202, """
                {"invocation_id":"inv_malformed_123","mode":"stream","status":"pending","deliverable_format":"markdown_brief"}
                """));
        server.createContext("/api/v1/tool-invocations/inv_malformed_123/events", exchange -> writeText(exchange, 200, "text/event-stream", """
                event: output_text
                data: {this is not valid json}

                """));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);

        var exception = org.junit.jupiter.api.Assertions.assertThrows(
                ApiException.class,
                () -> client.invokeDeepResearch("Trigger malformed SSE", "markdown_brief", false, true)
        );

        assertEquals("Relay returned invalid SSE JSON.", exception.getMessage());
        // Sensitive payload must be redacted in the body exposed by the exception.
        assertEquals("[redacted]", exception.responseBody());
    }

    // H-9: extractOutputText – nested response.output_text path -------------------

    @Test
    void wait_endpoint_reads_nested_response_output_text() throws Exception {
        // The relay wait endpoint may return a payload where output_text is nested
        // inside a "response" object rather than at the top level.
        server.createContext("/api/v1/tool-invocations/inv_nested/wait", exchange -> writeJson(exchange, 200, """
                {"invocation_id":"inv_nested","mode":"background","status":"completed","deliverable_format":"markdown_brief","response":{"output_text":"nested answer"}}
                """));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_nested");

        assertEquals("nested answer", result);
    }

    @Test
    void wait_endpoint_reads_output_array_with_content_blocks() throws Exception {
        // The relay wait endpoint may return an OpenAI-style output[] array with
        // content blocks of type "output_text".  extractOutputText must traverse it.
        server.createContext("/api/v1/tool-invocations/inv_output_array/wait", exchange -> writeJson(exchange, 200, """
                {"invocation_id":"inv_output_array","mode":"background","status":"completed","deliverable_format":"markdown_brief","output":[{"content":[{"type":"output_text","text":{"value":"array answer"}}]}]}
                """));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_output_array");

        assertEquals("array answer", result);
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
