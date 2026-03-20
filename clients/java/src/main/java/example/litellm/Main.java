package example.litellm;

import example.litellm.relay.RelayClient;
import java.time.Duration;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        String target = "direct";
        String api = "chat";
        boolean background = false;
        boolean stream = false;
        boolean webSearch = false;
        boolean autoToolCall = false;
        String deliverableFormat = "markdown_brief";
        Duration timeout = Duration.ofSeconds(30);

        java.util.List<String> promptParts = new java.util.ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--target" -> target = requireOptionValue(args, ++i, "--target");
                case "--api" -> api = requireOptionValue(args, ++i, "--api");
                case "--background" -> background = true;
                case "--stream" -> stream = true;
                case "--web-search" -> webSearch = true;
                case "--auto-tool-call" -> autoToolCall = true;
                case "--deliverable-format" -> deliverableFormat = requireOptionValue(args, ++i, "--deliverable-format");
                case "--timeout" -> timeout = Duration.ofSeconds(Long.parseLong(requireOptionValue(args, ++i, "--timeout")));
                default -> promptParts.add(args[i]);
            }
        }

        String prompt = promptParts.isEmpty()
                ? "Explain what the o3-deep-research model is useful for."
                : String.join(" ", promptParts);

        if (background && stream) {
            throw new IllegalArgumentException("--background and --stream cannot be combined.");
        }
        if (webSearch && !"responses".equals(api)) {
            throw new IllegalArgumentException("--web-search can only be used with --api responses.");
        }

        String content;
        if (autoToolCall) {
            if ("relay".equals(target)) {
                throw new IllegalArgumentException("--auto-tool-call cannot be combined with --target relay");
            }
            String relayUrl = System.getenv("RELAY_BASE_URL");
            if (relayUrl == null || relayUrl.isBlank()) {
                relayUrl = "http://127.0.0.1:8080";
            }
            EnvConfig config = EnvConfig.loadDefault();
            LiteLlmClient client = new LiteLlmClient(config.baseUrl(), config.apiKey(), config.model(), timeout);
            LiteLlmClient.ToolCallingResult result = client.createResponseWithToolCalling(prompt, relayUrl);
            content = result.finalText();
            if (result.toolCalled()) {
                System.err.println("[deep_research was called automatically]");
                System.err.println("response_id=" + result.responseId());
                System.err.println("previous_response_id=" + result.previousResponseId());
                System.err.println("tool_call_id=" + result.toolCallId());
                System.err.println("invocation_id=" + result.invocationId());
                System.err.println("upstream_response_id=" + result.upstreamResponseId());
            }
        } else if ("relay".equals(target)) {
            RelayClient client = new RelayClient(RelayClient.defaultBaseUrl(), timeout);
            content = client.invokeDeepResearch(prompt, deliverableFormat, background, stream);
        } else {
            if (background && !"responses".equals(api)) {
                throw new IllegalArgumentException("--background can only be used with --api responses");
            }
            if (stream) {
                throw new IllegalArgumentException("--stream is only supported with --target relay");
            }

            EnvConfig config = EnvConfig.loadDefault();
            LiteLlmClient client = new LiteLlmClient(config.baseUrl(), config.apiKey(), config.model(), timeout);
            if ("responses".equals(api)) {
                java.util.List<java.util.Map<String, Object>> tools = webSearch
                        ? java.util.List.of(java.util.Map.of("type", "web_search_preview"))
                        : null;
                content = client.createResponse(prompt, background, tools);
            } else {
                content = client.createChatCompletion(prompt);
            }
        }

        System.out.println(content);
    }

    private static String requireOptionValue(String[] args, int index, String optionName) {
        if (index >= args.length) {
            throw new IllegalArgumentException(optionName + " requires a value");
        }
        return args[index];
    }
}
