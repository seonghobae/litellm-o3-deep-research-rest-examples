package example.litellm;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class LiteLlmClient {
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(30);

    private final URI baseUrl;
    private final String apiKey;
    private final String model;
    private final Duration requestTimeout;
    private final HttpClient httpClient;

    public LiteLlmClient(String baseUrl, String apiKey, String model) {
        this(normalizeBaseUrl(baseUrl), apiKey, model, DEFAULT_TIMEOUT, HttpClient.newHttpClient());
    }

    public LiteLlmClient(String baseUrl, String apiKey, String model, Duration timeout) {
        this(normalizeBaseUrl(baseUrl), apiKey, model, timeout, HttpClient.newHttpClient());
    }

    LiteLlmClient(URI baseUrl, String apiKey, String model, HttpClient httpClient) {
        this(baseUrl, apiKey, model, DEFAULT_TIMEOUT, httpClient);
    }

    LiteLlmClient(URI baseUrl, String apiKey, String model, Duration timeout, HttpClient httpClient) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.model = model;
        this.requestTimeout = timeout;
        this.httpClient = httpClient;
    }

    public static URI normalizeBaseUrl(String raw) {
        try {
            URI parsed = new URI(raw);
            if (parsed.getScheme() == null || parsed.getHost() == null) {
                throw new IllegalArgumentException(
                        "LITELLM_BASE_URL must include a scheme and host, for example https://localhost:4000 or https://localhost:4000/v1.");
            }

            String path = parsed.getPath();
            if (path == null || path.isEmpty() || "/".equals(path)) {
                path = "/v1/";
            } else if ("/v1".equals(path) || "/v1/".equals(path)) {
                path = "/v1/";
            } else {
                throw new IllegalArgumentException(
                        "For this example, LITELLM_BASE_URL may only have an empty path or /v1.");
            }

            return new URI(parsed.getScheme(), parsed.getUserInfo(), parsed.getHost(), parsed.getPort(), path, null, null);
        } catch (URISyntaxException exception) {
            throw new IllegalArgumentException("LITELLM_BASE_URL is not a valid URI.", exception);
        }
    }

    public String createChatCompletion(String prompt) {
        JsonNode payload = postJson(
                baseUrl.resolve("chat/completions"),
                Map.of(
                        "model", model,
                        "messages", List.of(Map.of("role", "user", "content", prompt))));
        return extractAssistantText(payload);
    }

    public String createResponse(String prompt) {
        return createResponse(prompt, false, null);
    }

    public String createResponse(String prompt, boolean background) {
        return createResponse(prompt, background, null);
    }

    /**
     * Send a Responses API request with optional server-side tools.
     *
     * <p>Pass {@code tools = List.of(Map.of("type", "web_search_preview"))} to
     * enable real-time web search on models that support it (e.g. gpt-4o).
     * The LiteLLM Proxy must also have the tool enabled for the target model.
     *
     * @param prompt     user prompt
     * @param background submit as a background job and return raw metadata
     * @param tools      optional list of tool descriptors; {@code null} omits the field
     */
    public String createResponse(String prompt, boolean background, java.util.List<Map<String, Object>> tools) {
        Map<String, Object> requestPayload = new java.util.LinkedHashMap<>();
        requestPayload.put("model", model);
        requestPayload.put("input", prompt);
        if (background) {
            requestPayload.put("background", true);
        }
        if (tools != null && !tools.isEmpty()) {
            requestPayload.put("tools", tools);
        }

        JsonNode payload = postJson(
                baseUrl.resolve("responses"),
                requestPayload);

        if (background) {
            try {
                return MAPPER.writeValueAsString(payload);
            } catch (JsonProcessingException exception) {
                throw new IllegalStateException("Failed to serialize background response metadata.", exception);
            }
        }

        return extractResponseText(payload);
    }

    private static final java.util.Map<String, Object> DEEP_RESEARCH_TOOL_SCHEMA;

    static {
        java.util.Map<String, Object> params = new java.util.LinkedHashMap<>();
        params.put("type", "object");
        java.util.Map<String, Object> props = new java.util.LinkedHashMap<>();
        props.put("research_question", java.util.Map.of("type", "string"));
        props.put("deliverable_format", java.util.Map.of(
            "type", "string",
            "enum", java.util.List.of("markdown_brief", "markdown_report", "json_outline")
        ));
        params.put("properties", props);
        params.put("required", java.util.List.of("research_question", "deliverable_format"));

        java.util.Map<String, Object> fn = new java.util.LinkedHashMap<>();
        fn.put("name", "deep_research");
        fn.put("description", "Conduct in-depth research on a topic and return a detailed report.");
        fn.put("parameters", params);

        java.util.Map<String, Object> tool = new java.util.LinkedHashMap<>();
        tool.put("type", "function");
        tool.put("function", fn);

        DEEP_RESEARCH_TOOL_SCHEMA = java.util.Collections.unmodifiableMap(tool);
    }

    /**
     * Chat completions with automatic deep_research function calling.
     *
     * <p>Flow:
     * <ol>
     *   <li>First Chat Completions turn with the {@code deep_research} tool schema.</li>
     *   <li>If finish_reason is {@code tool_calls} for {@code deep_research}, calls the
     *       relay {@code POST /api/v1/chat} to execute the research.</li>
     *   <li>Second Chat Completions turn synthesises the final answer from the tool result.</li>
     * </ol>
     *
     * @param prompt       the user message
     * @param relayBaseUrl relay server base URL (e.g. {@code http://127.0.0.1:8080});
     *                     must NOT be null
     * @return array of length 2: {@code [finalAnswer, "true"|"false"]}
     */
    public String[] createChatWithToolCalling(String prompt, String relayBaseUrl) {
        // First turn
        java.util.Map<String, Object> payload = new java.util.LinkedHashMap<>();
        payload.put("model", model);
        payload.put("messages", java.util.List.of(java.util.Map.of("role", "user", "content", prompt)));
        payload.put("tools", java.util.List.of(DEEP_RESEARCH_TOOL_SCHEMA));

        JsonNode first = postJson(baseUrl.resolve("chat/completions"), payload);
        JsonNode choices = first.path("choices");
        if (!choices.isArray() || choices.isEmpty()) {
            throw new ApiException(200, "No choices in response.", first.toString());
        }
        JsonNode firstChoice = choices.get(0);
        String finishReason = firstChoice.path("finish_reason").asText("stop");
        JsonNode firstMessage = firstChoice.path("message");
        JsonNode toolCallsNode = firstMessage.path("tool_calls");

        // Locate the deep_research tool call
        JsonNode deepResearchCall = null;
        if ("tool_calls".equals(finishReason) && toolCallsNode.isArray()) {
            for (JsonNode tc : toolCallsNode) {
                if ("function".equals(tc.path("type").asText())
                        && "deep_research".equals(tc.path("function").path("name").asText())) {
                    deepResearchCall = tc;
                    break;
                }
            }
        }

        if (deepResearchCall == null) {
            // No tool call — return direct answer
            return new String[]{firstMessage.path("content").asText(""), "false"};
        }

        String toolCallId = deepResearchCall.path("id").asText("call_0");
        String rawArgs = deepResearchCall.path("function").path("arguments").asText("{}");
        JsonNode argsNode;
        try {
            argsNode = MAPPER.readTree(rawArgs);
        } catch (JsonProcessingException e) {
            argsNode = MAPPER.createObjectNode();
        }
        String researchQuestion = argsNode.path("research_question").asText(prompt);

        // Call relay /api/v1/chat
        String relayUrl = relayBaseUrl.endsWith("/") ? relayBaseUrl : relayBaseUrl + "/";
        URI relayUri = URI.create(relayUrl);
        java.util.Map<String, Object> relayBody = new java.util.LinkedHashMap<>();
        relayBody.put("message", researchQuestion);
        relayBody.put("auto_tool_call", true);
        JsonNode relayResp = postJson(relayUri.resolve("api/v1/chat"), relayBody);
        String researchSummary = relayResp.path("research_summary").isMissingNode() || relayResp.path("research_summary").isNull()
            ? relayResp.path("content").asText("")
            : relayResp.path("research_summary").asText("");

        // Second turn
        java.util.List<java.util.Map<String, Object>> messages2 = java.util.List.of(
            java.util.Map.of("role", "user", "content", prompt),
            buildAssistantWithToolCall(toolCallId, rawArgs),
            java.util.Map.of("role", "tool", "tool_call_id", toolCallId, "content", researchSummary)
        );
        java.util.Map<String, Object> second = new java.util.LinkedHashMap<>();
        second.put("model", model);
        second.put("messages", messages2);
        JsonNode secondResp = postJson(baseUrl.resolve("chat/completions"), second);
        JsonNode secondChoices = secondResp.path("choices");
        if (!secondChoices.isArray() || secondChoices.isEmpty()) {
            return new String[]{researchSummary, "true"};
        }
        String finalContent = secondChoices.get(0).path("message").path("content").asText(researchSummary);
        return new String[]{finalContent, "true"};
    }

    private static java.util.Map<String, Object> buildAssistantWithToolCall(String toolCallId, String rawArgs) {
        java.util.Map<String, Object> tc = new java.util.LinkedHashMap<>();
        tc.put("id", toolCallId);
        tc.put("type", "function");
        tc.put("function", java.util.Map.of("name", "deep_research", "arguments", rawArgs));
        java.util.Map<String, Object> msg = new java.util.LinkedHashMap<>();
        msg.put("role", "assistant");
        msg.put("content", "");
        msg.put("tool_calls", java.util.List.of(tc));
        return msg;
    }

    private JsonNode postJson(URI target, Map<String, Object> payload) {
        String body;
        try {
            body = MAPPER.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to serialize request payload.", exception);
        }

        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(requestTimeout)
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        HttpResponse<String> response;
        try {
            response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ApiException(-1, "Network error while calling LiteLLM: " + exception.getMessage(), null);
        } catch (IOException exception) {
            throw new ApiException(-1, "Network error while calling LiteLLM: " + exception.getMessage(), null);
        }

        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new ApiException(response.statusCode(), extractErrorMessage(response.body()), response.body());
        }

        try {
            return MAPPER.readTree(response.body());
        } catch (JsonProcessingException exception) {
            throw new ApiException(response.statusCode(), "LiteLLM responded with invalid JSON.", response.body());
        }
    }

    private static String extractErrorMessage(String body) {
        try {
            JsonNode payload = MAPPER.readTree(body);
            JsonNode error = payload.path("error");
            if (error.isObject()) {
                JsonNode message = error.get("message");
                if (message != null && message.isTextual() && !message.asText().isBlank()) {
                    return message.asText();
                }
            }
        } catch (JsonProcessingException ignored) {
            // Fall through to generic message.
        }
        return "LiteLLM returned an error response.";
    }

    private static String extractAssistantText(JsonNode payload) {
        JsonNode choices = payload.path("choices");
        if (!choices.isArray() || choices.isEmpty()) {
            throw new ApiException(200, "Response did not include any choices.", payload.toString());
        }

        JsonNode content = choices.get(0).path("message").path("content");
        if (content.isTextual() && !content.asText().isBlank()) {
            return content.asText();
        }
        if (content.isArray()) {
            StringBuilder builder = new StringBuilder();
            for (JsonNode block : content) {
                JsonNode text = block.get("text");
                if (text != null && text.isTextual()) {
                    builder.append(text.asText());
                }
            }
            if (!builder.isEmpty()) {
                return builder.toString();
            }
        }

        throw new ApiException(200, "Response did not include a usable assistant message.", payload.toString());
    }

    private static String extractResponseText(JsonNode payload) {
        JsonNode outputText = payload.get("output_text");
        if (outputText != null && outputText.isTextual() && !outputText.asText().isBlank()) {
            return outputText.asText();
        }

        JsonNode output = payload.path("output");
        if (!output.isArray() || output.isEmpty()) {
            throw new ApiException(200, "Response did not include any output items.", payload.toString());
        }

        StringBuilder builder = new StringBuilder();
        for (JsonNode item : output) {
            JsonNode content = item.path("content");
            if (!content.isArray()) {
                continue;
            }
            for (JsonNode block : content) {
                JsonNode type = block.get("type");
                if (type != null && type.isTextual() && !Set.of("output_text", "text").contains(type.asText())) {
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

        throw new ApiException(200, "Response did not include a usable text output.", payload.toString());
    }
}
