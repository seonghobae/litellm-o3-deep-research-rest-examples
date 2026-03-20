package example.litellm.relay;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import example.litellm.ApiException;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

public final class RelayClient {
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(30);

    private final URI baseUrl;
    private final Duration requestTimeout;
    private final HttpClient httpClient;

    public RelayClient(String baseUrl) {
        this(normalizeBaseUrl(baseUrl), DEFAULT_TIMEOUT, HttpClient.newHttpClient());
    }

    public RelayClient(String baseUrl, Duration timeout) {
        this(normalizeBaseUrl(baseUrl), timeout, HttpClient.newHttpClient());
    }

    RelayClient(URI baseUrl, HttpClient httpClient) {
        this(baseUrl, DEFAULT_TIMEOUT, httpClient);
    }

    RelayClient(URI baseUrl, Duration timeout, HttpClient httpClient) {
        this.baseUrl = baseUrl;
        this.requestTimeout = timeout;
        this.httpClient = httpClient;
    }

    public static String defaultBaseUrl() {
        String configured = System.getenv("RELAY_BASE_URL");
        if (configured == null || configured.isBlank()) {
            return "http://127.0.0.1:8080";
        }
        return configured.trim();
    }

    public static URI normalizeBaseUrl(String raw) {
        try {
            URI parsed = new URI(raw);
            if (parsed.getScheme() == null || parsed.getHost() == null) {
                throw new IllegalArgumentException(
                        "RELAY_BASE_URL must include a scheme and host, for example http://127.0.0.1:8080.");
            }

            String path = parsed.getPath();
            if (path == null || path.isEmpty()) {
                path = "/";
            }
            if (!path.endsWith("/")) {
                path = path + "/";
            }

            return new URI(parsed.getScheme(), parsed.getUserInfo(), parsed.getHost(), parsed.getPort(), path, null, null);
        } catch (URISyntaxException exception) {
            throw new IllegalArgumentException("RELAY_BASE_URL is not a valid URI.", exception);
        }
    }

    public String invokeDeepResearch(
            String researchQuestion,
            String deliverableFormat,
            boolean background,
            boolean stream) {
        if (background && stream) {
            throw new IllegalArgumentException("--background and --stream cannot both be used with relay mode");
        }

        JsonNode response = postJson(baseUrl.resolve("api/v1/tool-invocations"), buildInvocationPayload(
                researchQuestion,
                deliverableFormat,
                background,
                stream));

        if (stream) {
            return streamInvocation(requiredText(response, "invocation_id"));
        }
        if (background) {
            return response.toString();
        }
        return extractOutputText(response);
    }

    public String waitForInvocation(String invocationId) {
        JsonNode response = getJson(baseUrl.resolve("api/v1/tool-invocations/" + invocationId + "/wait"));
        return extractOutputText(response);
    }

    public String streamInvocation(String invocationId) {
        String body = getText(baseUrl.resolve("api/v1/tool-invocations/" + invocationId + "/events"), "text/event-stream");
        StringBuilder builder = new StringBuilder();
        for (String frame : body.split("\\R\\R")) {
            String trimmed = frame.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            for (String line : trimmed.split("\\R")) {
                if (!line.startsWith("data:")) {
                    continue;
                }
                String payload = line.substring("data:".length()).trim();
                try {
                    JsonNode event = MAPPER.readTree(payload);
                    JsonNode data = event.path("data");
                    JsonNode text = data.get("text");
                    if (text != null && text.isTextual()) {
                        builder.append(text.asText());
                    }
                } catch (JsonProcessingException exception) {
                    // Do not include raw SSE payload in message to avoid leaking sensitive data.
                    throw new ApiException(200, "Relay returned invalid SSE JSON.", "[redacted]");
                }
            }
        }
        return builder.toString();
    }

    private static Map<String, Object> buildInvocationPayload(
            String researchQuestion,
            String deliverableFormat,
            boolean background,
            boolean stream) {
        Map<String, Object> arguments = new LinkedHashMap<>();
        arguments.put("research_question", researchQuestion);
        arguments.put("deliverable_format", deliverableFormat);
        arguments.put("background", background);
        arguments.put("stream", stream);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tool_name", "deep_research");
        payload.put("arguments", arguments);
        return payload;
    }

    private JsonNode postJson(URI target, Map<String, Object> payload) {
        String body;
        try {
            body = MAPPER.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to serialize relay invocation payload.", exception);
        }

        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(requestTimeout)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();

        return sendJson(request);
    }

    private JsonNode getJson(URI target) {
        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(requestTimeout)
                .header("Accept", "application/json")
                .GET()
                .build();
        return sendJson(request);
    }

    private String getText(URI target, String accept) {
        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(requestTimeout)
                .header("Accept", accept)
                .GET()
                .build();
        HttpResponse<String> response = send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new ApiException(response.statusCode(), "Relay returned an error response.", response.body());
        }
        return response.body();
    }

    private JsonNode sendJson(HttpRequest request) {
        HttpResponse<String> response = send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new ApiException(response.statusCode(), "Relay returned an error response.", response.body());
        }
        try {
            return MAPPER.readTree(response.body());
        } catch (JsonProcessingException exception) {
            throw new ApiException(response.statusCode(), "Relay returned invalid JSON.", response.body());
        }
    }

    private <T> HttpResponse<T> send(HttpRequest request, HttpResponse.BodyHandler<T> handler) {
        try {
            return httpClient.send(request, handler);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ApiException(-1, "Network error while calling relay: " + exception.getMessage(), null);
        } catch (IOException exception) {
            throw new ApiException(-1, "Network error while calling relay: " + exception.getMessage(), null);
        }
    }

    private static String requiredText(JsonNode payload, String fieldName) {
        JsonNode value = payload.get(fieldName);
        if (value != null && value.isTextual() && !value.asText().isBlank()) {
            return value.asText();
        }
        throw new ApiException(200, "Relay response did not include " + fieldName + ".", payload.toString());
    }

    /**
     * Result from the relay {@code POST /api/v1/chat} endpoint.
     *
     * @param content          the assistant reply text
     * @param toolCalled       whether a tool was automatically invoked
     * @param toolName         the name of the tool that was called, or {@code null}
     * @param researchSummary  the research summary returned by the tool, or {@code null}
     */
    public record ChatResult(String content, boolean toolCalled, String toolName, String researchSummary) {}

    /**
     * POST /api/v1/chat — relay-side orchestration with optional deep_research tool.
     *
     * <p>This is equivalent to calling
     * {@code invokeChat(message, autoToolCall, null, "markdown_brief")}.
     *
     * @param message      user message
     * @param autoToolCall whether to enable automatic deep_research tool calling
     * @return ChatResult with content and tool metadata
     */
    public ChatResult invokeChat(String message, boolean autoToolCall) {
        return invokeChat(message, autoToolCall, null, "markdown_brief");
    }

    /**
     * POST /api/v1/chat — relay-side orchestration with optional deep_research tool,
     * system prompt, and deliverable format.
     *
     * <p>The {@code systemPrompt} is forwarded to the deep_research invocation as the
     * Responses API {@code instructions} field when the model triggers the tool.  Use
     * it to set a persona, output language, or answer format.
     *
     * <p>The {@code deliverableFormat} is the fallback format for the deep_research
     * invocation when the model does not specify one in its tool-call arguments.
     *
     * @param message          user message
     * @param autoToolCall     whether to enable automatic deep_research tool calling
     * @param systemPrompt     optional system-level instructions for deep_research
     *                         (maps to Responses API {@code instructions}); may be {@code null}
     * @param deliverableFormat fallback format for deep_research (default: {@code "markdown_brief"})
     * @return ChatResult with content and tool metadata
     */
    public ChatResult invokeChat(
            String message,
            boolean autoToolCall,
            String systemPrompt,
            String deliverableFormat) {
        java.util.Map<String, Object> body = new java.util.LinkedHashMap<>();
        body.put("message", message);
        body.put("auto_tool_call", autoToolCall);
        if (systemPrompt != null) {
            body.put("system_prompt", systemPrompt);
        }
        if (deliverableFormat != null && !deliverableFormat.isBlank()) {
            body.put("deliverable_format", deliverableFormat);
        }
        JsonNode result = postJson(chatUrl(), body);
        String content = result.path("content").asText("");
        boolean toolCalled = result.path("tool_called").asBoolean(false);
        String toolName = result.hasNonNull("tool_name") ? result.get("tool_name").asText() : null;
        String summary = result.hasNonNull("research_summary") ? result.get("research_summary").asText() : null;
        return new ChatResult(content, toolCalled, toolName, summary);
    }

    private URI chatUrl() {
        // baseUrl is like http://127.0.0.1:8080/ (trailing slash)
        return baseUrl.resolve("api/v1/chat");
    }

    private static String extractOutputText(JsonNode payload) {
        JsonNode outputText = payload.get("output_text");
        if (outputText != null && outputText.isTextual() && !outputText.asText().isBlank()) {
            return outputText.asText();
        }
        JsonNode response = payload.path("response");
        JsonNode nestedOutputText = response.get("output_text");
        if (nestedOutputText != null && nestedOutputText.isTextual() && !nestedOutputText.asText().isBlank()) {
            return nestedOutputText.asText();
        }
        JsonNode output = payload.path("output");
        if (output.isArray()) {
            StringBuilder builder = new StringBuilder();
            for (JsonNode item : output) {
                JsonNode content = item.path("content");
                if (!content.isArray()) {
                    continue;
                }
                for (JsonNode block : content) {
                    JsonNode type = block.get("type");
                    if (type != null && type.isTextual() && !java.util.Set.of("output_text", "text").contains(type.asText())) {
                        continue;
                    }
                    JsonNode text = block.get("text");
                    if (text == null) {
                        continue;
                    }
                    if (text.isTextual()) {
                        builder.append(text.asText());
                    } else if (text.isObject()) {
                        JsonNode value = text.get("value");
                        if (value != null && value.isTextual()) {
                            builder.append(value.asText());
                        }
                    }
                }
            }
            if (!builder.isEmpty()) {
                return builder.toString();
            }
        }
        throw new ApiException(200, "Relay response did not include a usable output_text value.", payload.toString());
    }
}
