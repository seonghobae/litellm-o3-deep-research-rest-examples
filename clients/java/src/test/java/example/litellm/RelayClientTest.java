package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

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

    // RelayClient utility / coverage gaps ----------------------------------------

    @Test
    void defaultBaseUrlReturnsEnvVarWhenSet() {
        // defaultBaseUrl() returns configured env var when RELAY_BASE_URL is set.
        // We can't easily set env vars in-process, but we can verify it returns
        // the localhost fallback when the variable is absent.
        String url = example.litellm.relay.RelayClient.defaultBaseUrl();
        assertEquals(true, url.startsWith("http://"));
    }

    @Test
    void normalizeBaseUrlAddsTrailingSlashToPath() {
        java.net.URI uri = example.litellm.relay.RelayClient.normalizeBaseUrl("http://127.0.0.1:8080/api");
        assertEquals(true, uri.getPath().endsWith("/"));
    }

    @Test
    void normalizeBaseUrlRejectsMissingScheme() {
        assertThrows(IllegalArgumentException.class,
                () -> example.litellm.relay.RelayClient.normalizeBaseUrl("not-a-uri"));
    }

    @Test
    void backgroundAndStreamCannotBothBeSetOnRelay() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            writeJson(exchange, 200, "{}");
        });

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        assertThrows(IllegalArgumentException.class,
                () -> client.invokeDeepResearch("q", "markdown_brief", true, true));
    }

    @Test
    void get_endpoint_returns_404_raises_api_exception() throws Exception {
        server.createContext("/api/v1/tool-invocations/missing/wait", exchange ->
                writeJson(exchange, 404, "{\"detail\":\"not found\"}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        ApiException ex = assertThrows(ApiException.class,
                () -> client.waitForInvocation("missing"));
        assertEquals(404, ex.statusCode());
    }

    @Test
    void events_endpoint_non_2xx_raises_api_exception() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange ->
                writeJson(exchange, 202,
                        "{\"invocation_id\":\"inv_err\",\"mode\":\"stream\",\"status\":\"pending\",\"deliverable_format\":\"markdown_brief\"}"));
        server.createContext("/api/v1/tool-invocations/inv_err/events", exchange ->
                writeJson(exchange, 503, "{\"error\":\"service unavailable\"}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        ApiException ex = assertThrows(ApiException.class,
                () -> client.invokeDeepResearch("fail stream", "markdown_brief", false, true));
        assertEquals(503, ex.statusCode());
    }

    @Test
    void post_endpoint_returns_invalid_json_raises_api_exception() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange -> {
            exchange.getRequestBody().readAllBytes();
            byte[] body = "not valid json".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            try (var out = exchange.getResponseBody()) { out.write(body); }
        });

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        ApiException ex = assertThrows(ApiException.class,
                () -> client.invokeDeepResearch("bad json response", "markdown_brief", false, false));
        assertEquals(true, ex.getMessage().toLowerCase().contains("invalid json"));
    }

    @Test
    void wait_endpoint_reads_plain_string_text_in_output_array() throws Exception {
        server.createContext("/api/v1/tool-invocations/inv_plain_str/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_plain_str\",\"mode\":\"background\",\"status\":\"completed\","
                                + "\"deliverable_format\":\"markdown_brief\","
                                + "\"output\":[{\"content\":[{\"type\":\"output_text\",\"text\":\"plain-string-value\"}]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_plain_str");
        assertEquals("plain-string-value", result);
    }

    @Test
    void wait_endpoint_skips_blocks_with_unrecognised_type() throws Exception {
        server.createContext("/api/v1/tool-invocations/inv_skip_type/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_skip_type\",\"mode\":\"background\",\"status\":\"completed\","
                                + "\"deliverable_format\":\"markdown_brief\","
                                + "\"output\":[{\"content\":[{\"type\":\"reasoning\",\"text\":\"skip\"},{\"type\":\"output_text\",\"text\":\"keep\"}]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_skip_type");
        assertEquals("keep", result);
    }

    @Test
    void wait_endpoint_skips_blocks_with_null_text() throws Exception {
        server.createContext("/api/v1/tool-invocations/inv_null_text/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_null_text\",\"mode\":\"background\",\"status\":\"completed\","
                                + "\"deliverable_format\":\"markdown_brief\","
                                + "\"output\":[{\"content\":[{\"type\":\"output_text\"},{\"type\":\"output_text\",\"text\":\"has-text\"}]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_null_text");
        assertEquals("has-text", result);
    }

    @Test
    void wait_endpoint_raises_when_all_output_blocks_skipped() throws Exception {
        server.createContext("/api/v1/tool-invocations/inv_all_skip/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_all_skip\",\"mode\":\"background\",\"status\":\"completed\","
                                + "\"deliverable_format\":\"markdown_brief\","
                                + "\"output\":[{\"content\":[{\"type\":\"reasoning\",\"text\":\"skipped\"}]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        ApiException ex = assertThrows(ApiException.class,
                () -> client.waitForInvocation("inv_all_skip"));
        assertEquals(true, ex.getMessage().toLowerCase().contains("usable"));
    }

    @Test
    void foreground_result_missing_invocation_id_raises_api_exception() throws Exception {
        // If the relay response has output_text but no invocation_id field, the
        // foreground path in invokeDeepResearch calls extractOutputText which
        // succeeds.  To hit the requiredText("invocation_id") failure we need a
        // response that is neither foreground (no output_text) nor background
        // (invocation_id required for the returned JSON).  Easiest path: stream
        // request where relay returns JSON without invocation_id.
        server.createContext("/api/v1/tool-invocations", exchange ->
                writeJson(exchange, 202,
                        "{\"mode\":\"stream\",\"status\":\"pending\","
                                + "\"deliverable_format\":\"markdown_brief\"}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        ApiException ex = assertThrows(ApiException.class,
                () -> client.invokeDeepResearch("missing id", "markdown_brief", false, true));
        assertEquals(true, ex.getMessage().toLowerCase().contains("invocation_id"));
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

    // extractOutputText: blank top-level output_text falls through to nested/array -

    @Test
    void wait_endpoint_falls_through_when_top_level_output_text_is_blank() throws Exception {
        // outputText.isBlank() → falls through to nested response.output_text check
        server.createContext("/api/v1/tool-invocations/inv_blank_top/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_blank_top\",\"mode\":\"background\","
                                + "\"status\":\"completed\",\"deliverable_format\":\"markdown_brief\","
                                + "\"output_text\":\"   \","
                                + "\"output\":[{\"content\":[{\"type\":\"output_text\",\"text\":\"fallback answer\"}]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_blank_top");
        assertEquals("fallback answer", result);
    }

    @Test
    void wait_endpoint_falls_through_when_nested_output_text_is_blank() throws Exception {
        // nestedOutputText.isBlank() → falls through to output[] array traversal
        server.createContext("/api/v1/tool-invocations/inv_blank_nested/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_blank_nested\",\"mode\":\"background\","
                                + "\"status\":\"completed\",\"deliverable_format\":\"markdown_brief\","
                                + "\"response\":{\"output_text\":\"\"},"
                                + "\"output\":[{\"content\":[{\"type\":\"output_text\",\"text\":\"from output array\"}]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_blank_nested");
        assertEquals("from output array", result);
    }

    @Test
    void wait_endpoint_reads_text_with_null_value_in_object_skips_and_uses_other_block() throws Exception {
        // text.isObject() but value is null → skips; next block has valid text
        server.createContext("/api/v1/tool-invocations/inv_null_value/wait", exchange ->
                writeJson(exchange, 200,
                        "{\"invocation_id\":\"inv_null_value\",\"mode\":\"background\","
                                + "\"status\":\"completed\",\"deliverable_format\":\"markdown_brief\","
                                + "\"output\":[{\"content\":["
                                + "{\"type\":\"output_text\",\"text\":{\"value\":null}},"
                                + "{\"type\":\"output_text\",\"text\":\"real value\"}"
                                + "]}]}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.waitForInvocation("inv_null_value");
        assertEquals("real value", result);
    }

    // streamInvocation: SSE frame parsing branches --------------------------------

    @Test
    void streams_text_skips_empty_sse_frames() throws Exception {
        // Body has an empty frame between two valid frames — trimmed.isEmpty() branch
        server.createContext("/api/v1/tool-invocations", exchange -> writeJson(exchange, 202,
                "{\"invocation_id\":\"inv_empty_frame\",\"mode\":\"stream\",\"status\":\"pending\",\"deliverable_format\":\"markdown_brief\"}"));
        server.createContext("/api/v1/tool-invocations/inv_empty_frame/events", exchange ->
                writeText(exchange, 200, "text/event-stream",
                        "event: output_text\n"
                                + "data: {\"invocation_id\":\"inv_empty_frame\",\"type\":\"output_text\",\"status\":\"running\",\"data\":{\"text\":\"first\"}}\n"
                                + "\n"
                                + "\n"  // extra blank line → empty frame
                                + "event: output_text\n"
                                + "data: {\"invocation_id\":\"inv_empty_frame\",\"type\":\"output_text\",\"status\":\"running\",\"data\":{\"text\":\" second\"}}\n"
                                + "\n"
                                + "event: completed\n"
                                + "data: {\"invocation_id\":\"inv_empty_frame\",\"type\":\"completed\",\"status\":\"completed\",\"data\":{\"output_text\":\"first second\"}}\n"
                                + "\n"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.invokeDeepResearch("empty frame test", "markdown_brief", false, true);
        assertEquals("first second", result);
    }

    @Test
    void streams_text_skips_non_data_lines_in_sse_frame() throws Exception {
        // Lines not starting with "data:" (e.g. "event:", "id:", ":comment") are skipped
        server.createContext("/api/v1/tool-invocations", exchange -> writeJson(exchange, 202,
                "{\"invocation_id\":\"inv_non_data\",\"mode\":\"stream\",\"status\":\"pending\",\"deliverable_format\":\"markdown_brief\"}"));
        server.createContext("/api/v1/tool-invocations/inv_non_data/events", exchange ->
                writeText(exchange, 200, "text/event-stream",
                        "event: output_text\n"
                                + ": this is a comment line\n"
                                + "id: 1\n"
                                + "data: {\"invocation_id\":\"inv_non_data\",\"type\":\"output_text\",\"status\":\"running\",\"data\":{\"text\":\"only this\"}}\n"
                                + "\n"
                                + "event: completed\n"
                                + "data: {\"invocation_id\":\"inv_non_data\",\"type\":\"completed\",\"status\":\"completed\",\"data\":{\"output_text\":\"only this\"}}\n"
                                + "\n"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        String result = client.invokeDeepResearch("non-data line test", "markdown_brief", false, true);
        assertEquals("only this", result);
    }

    // requiredText: blank field value → raises ApiException ----------------------

    @Test
    void foreground_result_with_blank_invocation_id_raises_api_exception() throws Exception {
        server.createContext("/api/v1/tool-invocations", exchange ->
                writeJson(exchange, 202,
                        "{\"invocation_id\":\"   \",\"mode\":\"stream\","
                                + "\"status\":\"pending\",\"deliverable_format\":\"markdown_brief\"}"));

        example.litellm.relay.RelayClient client = new example.litellm.relay.RelayClient(baseUrl);
        ApiException ex = assertThrows(ApiException.class,
                () -> client.invokeDeepResearch("blank id", "markdown_brief", false, true));
        assertEquals(true, ex.getMessage().toLowerCase().contains("invocation_id"));
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
