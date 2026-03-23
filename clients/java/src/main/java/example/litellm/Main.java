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
                case "--help", "-h" -> {
                    printHelp();
                    return;
                }
                case "--target" -> target = requireOptionValue(args, ++i, "--target");
                case "--api" -> api = requireOptionValue(args, ++i, "--api");
                case "--background" -> background = true;
                case "--stream" -> stream = true;
                case "--web-search" -> webSearch = true;
                case "--auto-tool-call" -> autoToolCall = true;
                case "--deliverable-format" -> deliverableFormat = requireOptionValue(args, ++i, "--deliverable-format");
                case "--timeout" -> timeout = parseTimeoutSeconds(requireOptionValue(args, ++i, "--timeout"));
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
                System.err.println("invocation_token=" + result.invocationToken());
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

    static Duration parseTimeoutSeconds(String raw) {
        final long seconds;
        try {
            seconds = Long.parseLong(raw);
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(
                    "--timeout must be a positive integer number of seconds: " + raw,
                    exception);
        }
        if (seconds <= 0) {
            throw new IllegalArgumentException(
                    "--timeout must be greater than 0 seconds: " + raw);
        }
        return Duration.ofSeconds(seconds);
    }

    private static void printHelp() {
        System.out.println("Usage: java -jar litellm-o3-deep-research-java-0.1.0.jar [options] [prompt]");
        System.out.println("Options:");
        System.out.println("  --help, -h                 Show this help message and exit.");
        System.out.println("  --api <chat|responses>    Which OpenAI-compatible endpoint to use.");
        System.out.println("  --background              Request server-side background processing for responses.");
        System.out.println("  --web-search              Attach web_search_preview to a responses call.");
        System.out.println("  --auto-tool-call          Use Responses function calling with deep_research.");
        System.out.println("  --timeout <seconds>       Positive integer request timeout in seconds.");
        System.out.println("  --target relay            Call the relay example instead of direct LiteLLM.");
        System.out.println("  --stream                  Use relay SSE streaming mode.");
        System.out.println("  --deliverable-format <format>  Set relay deliverable format.");
    }
}
