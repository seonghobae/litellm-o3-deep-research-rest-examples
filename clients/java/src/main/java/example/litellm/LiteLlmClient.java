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

    private final URI baseUrl;
    private final String apiKey;
    private final String model;
    private final HttpClient httpClient;

    public LiteLlmClient(String baseUrl, String apiKey, String model) {
        this(normalizeBaseUrl(baseUrl), apiKey, model, HttpClient.newHttpClient());
    }

    LiteLlmClient(URI baseUrl, String apiKey, String model, HttpClient httpClient) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.model = model;
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
        return createResponse(prompt, false);
    }

    public String createResponse(String prompt, boolean background) {
        Map<String, Object> requestPayload = new java.util.LinkedHashMap<>();
        requestPayload.put("model", model);
        requestPayload.put("input", prompt);
        if (background) {
            requestPayload.put("background", true);
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

    private JsonNode postJson(URI target, Map<String, Object> payload) {
        String body;
        try {
            body = MAPPER.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to serialize request payload.", exception);
        }

        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(Duration.ofSeconds(30))
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
