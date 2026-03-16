package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class EnvConfigTest {

    @TempDir
    Path tempDir;

    @Test
    void readsValuesFromDotenvWhenEnvironmentMissing() throws Exception {
        Path dotenv = tempDir.resolve("test.env");
        Files.writeString(
                dotenv,
                "LITELLM_BASE_URL=https://example.com\n"
                        + "LITELLM_API_KEY=sk-from-file\n"
                        + "LITELLM_MODEL=o3-deep-research\n");

        EnvConfig config = EnvConfig.load(dotenv, Map.of());

        assertEquals("https://example.com", config.baseUrl());
        assertEquals("sk-from-file", config.apiKey());
        assertEquals("o3-deep-research", config.model());
    }

    @Test
    void environmentValuesOverrideDotenv() throws Exception {
        Path dotenv = tempDir.resolve("test.env");
        Files.writeString(
                dotenv,
                "LITELLM_BASE_URL=https://dotenv.example\n"
                        + "LITELLM_API_KEY=sk-from-file\n");

        EnvConfig config = EnvConfig.load(
                dotenv,
                Map.of(
                        "LITELLM_BASE_URL", "https://env.example",
                        "LITELLM_API_KEY", "sk-from-env",
                        "LITELLM_MODEL", "custom-model"));

        assertEquals("https://env.example", config.baseUrl());
        assertEquals("sk-from-env", config.apiKey());
        assertEquals("custom-model", config.model());
    }

    @Test
    void missingRequiredValuesFailFast() throws Exception {
        Path dotenv = tempDir.resolve("empty.env");
        Files.writeString(dotenv, "", java.nio.charset.StandardCharsets.UTF_8);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> EnvConfig.load(dotenv, Map.of()));

        assertEquals(true, error.getMessage().contains("LITELLM_BASE_URL"));
    }
}
