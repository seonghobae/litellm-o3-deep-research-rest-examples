package example.litellm;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        String api = "chat";
        int promptStart = 0;
        if (args.length >= 2 && "--api".equals(args[0])) {
            api = args[1];
            promptStart = 2;
        }

        String prompt = args.length > promptStart
                ? String.join(" ", java.util.Arrays.copyOfRange(args, promptStart, args.length))
                : "Explain what the o3-deep-research model is useful for.";

        EnvConfig config = EnvConfig.loadDefault();
        LiteLlmClient client = new LiteLlmClient(config.baseUrl(), config.apiKey(), config.model());

        String content = "responses".equals(api)
                ? client.createResponse(prompt)
                : client.createChatCompletion(prompt);

        System.out.println(content);
    }
}
