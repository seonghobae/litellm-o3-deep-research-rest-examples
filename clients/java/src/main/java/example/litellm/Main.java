package example.litellm;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        String prompt = args.length > 0 ? String.join(" ", args) : "Explain what the o3-deep-research model is useful for.";
        EnvConfig config = EnvConfig.loadDefault();
        LiteLlmClient client = new LiteLlmClient(config.baseUrl(), config.apiKey(), config.model());
        System.out.println(client.createChatCompletion(prompt));
    }
}
