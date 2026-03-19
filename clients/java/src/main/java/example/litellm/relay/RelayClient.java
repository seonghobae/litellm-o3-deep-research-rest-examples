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
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(30);

    private final URI baseUrl;
    private final HttpClient httpClient;

    public RelayClient(String baseUrl) {
        this(normalizeBaseUrl(baseUrl), HttpClient.newHttpClient());
    }

    RelayClient(URI baseUrl, HttpClient httpClient) {
        this.baseUrl = baseUrl;
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
                .timeout(REQUEST_TIMEOUT)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();

        return sendJson(request);
    }

    private JsonNode getJson(URI target) {
        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(REQUEST_TIMEOUT)
                .header("Accept", "application/json")
                .GET()
                .build();
        return sendJson(request);
    }

    private String getText(URI target, String accept) {
        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(REQUEST_TIMEOUT)
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
