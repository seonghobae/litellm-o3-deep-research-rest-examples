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

            String scheme = parsed.getScheme().toLowerCase(java.util.Locale.ROOT);
            if (!"https".equals(scheme) && !"http".equals(scheme)) {
                throw new IllegalArgumentException("LITELLM_BASE_URL must use https or http.");
            }

            String host = parsed.getHost();
            if ("http".equals(scheme) && !"localhost".equalsIgnoreCase(host) && !"127.0.0.1".equals(host)) {
                throw new IllegalArgumentException(
                        "For security reasons this example only permits http URLs for localhost. Use https for remote LiteLLM endpoints.");
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

            return new URI(scheme, parsed.getUserInfo(), host, parsed.getPort(), path, null, null);
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

        java.util.Map<String, Object> tool = new java.util.LinkedHashMap<>();
        tool.put("type", "function");
        tool.put("name", "deep_research");
        tool.put("description", "Conduct in-depth research on a topic and return a detailed report.");
        tool.put("parameters", params);

        DEEP_RESEARCH_TOOL_SCHEMA = java.util.Collections.unmodifiableMap(tool);
    }

    /** Responses API 표준 function calling 결과와 deep_research 메타데이터를 담는다. */
    public record ToolCallingResult(
            String finalText,
            boolean toolCalled,
            String responseId,
            String previousResponseId,
            String responseStatus,
            String toolName,
            String toolCallId,
            String invocationId,
            String upstreamResponseId,
            String researchSummary) {}

    /**
     * Responses API 표준 function calling으로 deep_research를 실행한다.
     *
     * @param prompt user prompt
     * @param relayBaseUrl relay base URL for deep_research execution
     * @return 최종 텍스트와 관련 key를 포함한 결과 객체
     */
    public ToolCallingResult createResponseWithToolCalling(String prompt, String relayBaseUrl) {
        java.util.Map<String, Object> payload = new java.util.LinkedHashMap<>();
        payload.put("model", model);
        payload.put("input", prompt);
        payload.put("tools", java.util.List.of(DEEP_RESEARCH_TOOL_SCHEMA));

        JsonNode first = postJson(baseUrl.resolve("responses"), payload);
        String firstResponseId = textOrNull(first.get("id"));
        String firstStatus = textOrNull(first.get("status"));
        JsonNode output = first.path("output");
        if (!output.isArray()) {
            throw new ApiException(200, "Response did not include any output items.", first.toString());
        }

        JsonNode deepResearchCall = null;
        for (JsonNode item : output) {
            if ("function_call".equals(item.path("type").asText())
                    && "deep_research".equals(item.path("name").asText())) {
                deepResearchCall = item;
                break;
            }
        }

        if (deepResearchCall == null) {
            return new ToolCallingResult(
                    extractResponseText(first),
                    false,
                    firstResponseId,
                    null,
                    firstStatus,
                    null,
                    null,
                    null,
                    null,
                    null);
        }

        String toolCallId = deepResearchCall.path("call_id").asText("call_0");
        String rawArgs = deepResearchCall.path("arguments").asText("{}");
        JsonNode argsNode;
        try {
            argsNode = MAPPER.readTree(rawArgs);
        } catch (JsonProcessingException e) {
            argsNode = MAPPER.createObjectNode();
        }

        String researchQuestion = argsNode.path("research_question").asText(prompt);
        String deliverableFormat = argsNode.path("deliverable_format").asText("markdown_brief");

        String relayUrl = relayBaseUrl.endsWith("/") ? relayBaseUrl : relayBaseUrl + "/";
        URI relayUri = URI.create(relayUrl);
        java.util.Map<String, Object> relayBody = new java.util.LinkedHashMap<>();
        relayBody.put("tool_name", "deep_research");
        relayBody.put(
                "arguments",
                java.util.Map.of(
                        "research_question", researchQuestion,
                        "deliverable_format", deliverableFormat,
                        "background", false,
                        "stream", false));
        JsonNode relayResp = postJson(relayUri.resolve("api/v1/tool-invocations"), relayBody, false);
        String researchSummary = extractRelayOutputText(relayResp);

        java.util.Map<String, Object> secondPayload = new java.util.LinkedHashMap<>();
        secondPayload.put("model", model);
        secondPayload.put("previous_response_id", firstResponseId);
        secondPayload.put(
                "input",
                java.util.List.of(
                        java.util.Map.of(
                                "type", "function_call_output",
                                "call_id", toolCallId,
                                "output", researchSummary)));

        JsonNode second = postJson(baseUrl.resolve("responses"), secondPayload);
        String finalText;
        try {
            finalText = extractResponseText(second);
        } catch (ApiException exception) {
            finalText = researchSummary;
        }

        return new ToolCallingResult(
                finalText,
                true,
                textOrNull(second.get("id")),
                firstResponseId,
                textOrNull(second.get("status")),
                "deep_research",
                toolCallId,
                textOrNull(relayResp.get("invocation_id")),
                textOrNull(relayResp.get("upstream_response_id")),
                researchSummary);
    }

    /**
     * Chat completions-style compatibility wrapper around the Responses API auto tool-calling flow.
     *
     * <p>Flow:
     * <ol>
     *   <li>First Responses API turn with the {@code deep_research} tool schema.</li>
     *   <li>If the response emits a {@code function_call} for {@code deep_research}, calls the
     *       relay {@code POST /api/v1/tool-invocations} endpoint to execute the research.</li>
     *   <li>Second Responses API turn sends a standard {@code function_call_output} item and
     *       synthesises the final answer from the tool result.</li>
     * </ol>
     *
     * @param prompt       the user message
     * @param relayBaseUrl relay server base URL (e.g. {@code http://127.0.0.1:8080});
     *                     must NOT be null
     * @return array of length 2: {@code [finalAnswer, "true"|"false"]}
     */
    public String[] createChatWithToolCalling(String prompt, String relayBaseUrl) {
        ToolCallingResult result = createResponseWithToolCalling(prompt, relayBaseUrl);
        return new String[] {result.finalText(), Boolean.toString(result.toolCalled())};
    }

    private static JsonNode extractFunctionCall(JsonNode payload) {
        JsonNode output = payload.path("output");
        if (!output.isArray()) {
            throw new ApiException(200, "Response did not include any output items.", payload.toString());
        }
        for (JsonNode item : output) {
            if (!"function_call".equals(item.path("type").asText())) {
                continue;
            }
            if (!"deep_research".equals(item.path("name").asText())) {
                continue;
            }
            return item;
        }
        return null;
    }

    private static String extractResponseId(JsonNode payload) {
        JsonNode responseId = payload.get("id");
        if (responseId != null && responseId.isTextual() && !responseId.asText().isBlank()) {
            return responseId.asText();
        }
        throw new ApiException(200, "Response did not include a usable id.", payload.toString());
    }

    private JsonNode postJson(URI target, Map<String, Object> payload) {
        return postJson(target, payload, true);
    }

    private JsonNode postJson(URI target, Map<String, Object> payload, boolean includeAuth) {
        String body;
        try {
            body = MAPPER.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to serialize request payload.", exception);
        }

        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder(target)
                .timeout(requestTimeout)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json");
        if (includeAuth) {
            requestBuilder.header("Authorization", "Bearer " + apiKey);
        }
        HttpRequest request = requestBuilder
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

    private static String extractRelayOutputText(JsonNode payload) {
        JsonNode outputText = payload.get("output_text");
        if (outputText != null && outputText.isTextual() && !outputText.asText().isBlank()) {
            return outputText.asText();
        }
        JsonNode response = payload.path("response");
        JsonNode nestedOutputText = response.get("output_text");
        if (nestedOutputText != null && nestedOutputText.isTextual() && !nestedOutputText.asText().isBlank()) {
            return nestedOutputText.asText();
        }
        throw new ApiException(200, "Relay response did not include a usable output_text value.", payload.toString());
    }

    private static String textOrNull(JsonNode node) {
        if (node != null && node.isTextual() && !node.asText().isBlank()) {
            return node.asText();
        }
        return null;
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
