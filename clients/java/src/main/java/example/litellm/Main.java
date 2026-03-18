package example.litellm;

import example.litellm.relay.RelayClient;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        String target = "direct";
        String api = "chat";
        boolean background = false;
        boolean stream = false;
        String deliverableFormat = "markdown_brief";

        java.util.List<String> promptParts = new java.util.ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--target" -> target = requireOptionValue(args, ++i, "--target");
                case "--api" -> api = requireOptionValue(args, ++i, "--api");
                case "--background" -> background = true;
                case "--stream" -> stream = true;
                case "--deliverable-format" -> deliverableFormat = requireOptionValue(args, ++i, "--deliverable-format");
                default -> promptParts.add(args[i]);
            }
        }

        String prompt = promptParts.isEmpty()
                ? "Explain what the o3-deep-research model is useful for."
                : String.join(" ", promptParts);

        if (background && stream) {
            throw new IllegalArgumentException("--background and --stream cannot be combined.");
        }

        String content;
        if ("relay".equals(target)) {
            RelayClient client = new RelayClient(RelayClient.defaultBaseUrl());
            content = client.invokeDeepResearch(prompt, deliverableFormat, background, stream);
        } else {
            if (background && !"responses".equals(api)) {
                throw new IllegalArgumentException("--background can only be used with --api responses");
            }
            if (stream) {
                throw new IllegalArgumentException("--stream is only supported with --target relay");
            }

            EnvConfig config = EnvConfig.loadDefault();
            LiteLlmClient client = new LiteLlmClient(config.baseUrl(), config.apiKey(), config.model());
            content = "responses".equals(api)
                    ? client.createResponse(prompt, background)
                    : client.createChatCompletion(prompt);
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
