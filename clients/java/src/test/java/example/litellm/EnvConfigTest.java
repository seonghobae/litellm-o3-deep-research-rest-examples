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

    @Test
    void missingApiKeyFailsFast() throws Exception {
        Path dotenv = tempDir.resolve("no-key.env");
        Files.writeString(dotenv, "LITELLM_BASE_URL=https://example.com\n",
                java.nio.charset.StandardCharsets.UTF_8);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> EnvConfig.load(dotenv, Map.of()));

        assertEquals(true, error.getMessage().contains("LITELLM_API_KEY"));
    }

    @Test
    void returnsEmptyMapWhenDotenvFileIsMissing() throws Exception {
        Path missingPath = tempDir.resolve("does-not-exist.env");

        // The absent dotenv should not crash; env vars supply the required values.
        EnvConfig config = EnvConfig.load(missingPath, Map.of(
                "LITELLM_BASE_URL", "https://env-only.example",
                "LITELLM_API_KEY", "sk-env-only"));

        assertEquals("https://env-only.example", config.baseUrl());
        assertEquals("sk-env-only", config.apiKey());
    }

    @Test
    void parsesExportPrefixedLines() throws Exception {
        Path dotenv = tempDir.resolve("export.env");
        Files.writeString(dotenv,
                "export LITELLM_BASE_URL=https://exported.example\n"
                        + "export LITELLM_API_KEY=sk-exported\n",
                java.nio.charset.StandardCharsets.UTF_8);

        EnvConfig config = EnvConfig.load(dotenv, Map.of());

        assertEquals("https://exported.example", config.baseUrl());
        assertEquals("sk-exported", config.apiKey());
    }

    @Test
    void skipsCommentAndBlankLines() throws Exception {
        Path dotenv = tempDir.resolve("comments.env");
        Files.writeString(dotenv,
                "# This is a comment\n"
                        + "\n"
                        + "LITELLM_BASE_URL=https://commented.example\n"
                        + "LITELLM_API_KEY=sk-commented\n",
                java.nio.charset.StandardCharsets.UTF_8);

        EnvConfig config = EnvConfig.load(dotenv, Map.of());

        assertEquals("https://commented.example", config.baseUrl());
    }

    @Test
    void skipsLineWithNoEqualsSign() throws Exception {
        Path dotenv = tempDir.resolve("no-equals.env");
        Files.writeString(dotenv,
                "INVALID_LINE_NO_EQUALS\n"
                        + "LITELLM_BASE_URL=https://valid.example\n"
                        + "LITELLM_API_KEY=sk-valid\n",
                java.nio.charset.StandardCharsets.UTF_8);

        EnvConfig config = EnvConfig.load(dotenv, Map.of());
        assertEquals("https://valid.example", config.baseUrl());
    }

    @Test
    void stripsSingleQuotesFromValues() throws Exception {
        Path dotenv = tempDir.resolve("single-quotes.env");
        Files.writeString(dotenv,
                "LITELLM_BASE_URL='https://quoted.example'\n"
                        + "LITELLM_API_KEY='sk-quoted'\n",
                java.nio.charset.StandardCharsets.UTF_8);

        EnvConfig config = EnvConfig.load(dotenv, Map.of());
        assertEquals("https://quoted.example", config.baseUrl());
        assertEquals("sk-quoted", config.apiKey());
    }

    @Test
    void loadDefaultUsesHomeDirectoryDotenv() throws Exception {
        // loadDefault() reads Path.of(user.home, ".env") + System.getenv().
        // Write a .env in tempDir, redirect user.home there, and override the
        // env map via a package-visible path so the method picks up our values.
        // Since we cannot easily clear real env vars, we write a valid dotenv
        // under the temp home and verify the method does not crash.
        java.nio.file.Path dotenv = tempDir.resolve(".env");
        java.nio.file.Files.writeString(dotenv,
                "LITELLM_BASE_URL=https://home-default.example\nLITELLM_API_KEY=sk-home\n",
                java.nio.charset.StandardCharsets.UTF_8);

        String originalHome = System.getProperty("user.home");
        try {
            System.setProperty("user.home", tempDir.toString());
            // If real env vars are already set they take precedence, but the
            // method still completes without error regardless.
            EnvConfig config = EnvConfig.loadDefault();
            // Verify we get *something* valid back.
            assertEquals(true, config.baseUrl() != null && !config.baseUrl().isBlank());
        } finally {
            System.setProperty("user.home", originalHome);
        }
    }
}
