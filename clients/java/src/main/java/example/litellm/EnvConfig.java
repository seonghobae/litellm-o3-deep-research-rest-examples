package example.litellm;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public record EnvConfig(String baseUrl, String apiKey, String model) {

    public static EnvConfig loadDefault() {
        return load(Path.of(System.getProperty("user.home"), ".env"), System.getenv());
    }

    static EnvConfig load(Path dotenvPath, Map<String, String> env) {
        Map<String, String> values = new HashMap<>();
        values.putAll(readDotenv(dotenvPath));
        values.putAll(env);

        String baseUrl = values.get("LITELLM_BASE_URL");
        String apiKey = values.get("LITELLM_API_KEY");
        String model = values.getOrDefault("LITELLM_MODEL", "o3-deep-research");

        if (isBlank(baseUrl)) {
            throw new IllegalStateException(
                    "LITELLM_BASE_URL is not set. Configure it in the environment or ~/.env.");
        }
        if (isBlank(apiKey)) {
            throw new IllegalStateException(
                    "LITELLM_API_KEY is not set. Configure it in the environment or ~/.env.");
        }

        return new EnvConfig(baseUrl.trim(), apiKey.trim(), isBlank(model) ? "o3-deep-research" : model.trim());
    }

    private static Map<String, String> readDotenv(Path dotenvPath) {
        Map<String, String> values = new HashMap<>();
        if (!Files.isRegularFile(dotenvPath)) {
            return values;
        }

        List<String> lines;
        try {
            lines = Files.readAllLines(dotenvPath, StandardCharsets.UTF_8);
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to read dotenv file: " + dotenvPath, exception);
        }

        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            if (trimmed.startsWith("export ")) {
                trimmed = trimmed.substring("export ".length()).trim();
            }

            int separator = trimmed.indexOf('=');
            if (separator <= 0) {
                continue;
            }

            String key = trimmed.substring(0, separator).trim();
            String value = trimmed.substring(separator + 1).trim();
            if ((value.startsWith("\"") && value.endsWith("\""))
                    || (value.startsWith("'") && value.endsWith("'"))) {
                value = value.substring(1, value.length() - 1);
            }
            values.put(key, value);
        }

        return values;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
