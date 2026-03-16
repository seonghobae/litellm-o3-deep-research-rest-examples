package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class UrlNormalizationTest {

    @ParameterizedTest
    @ValueSource(strings = {
        "https://example.com",
        "https://example.com/",
        "https://example.com/v1",
        "https://example.com/v1/"
    })
    void normalizesRootAndV1(String raw) {
        assertEquals("https://example.com/v1/", LiteLlmClient.normalizeBaseUrl(raw).toString());
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "example.com",
        "https://example.com/api",
        "https://example.com/v2"
    })
    void rejectsUnexpectedPaths(String raw) {
        assertThrows(IllegalArgumentException.class, () -> LiteLlmClient.normalizeBaseUrl(raw));
    }
}
