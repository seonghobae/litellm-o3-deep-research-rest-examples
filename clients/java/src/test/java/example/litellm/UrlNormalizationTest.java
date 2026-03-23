package example.litellm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
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
    @CsvSource({
        "http://localhost, http://localhost/v1/",
        "http://localhost/, http://localhost/v1/",
        "http://localhost/v1, http://localhost/v1/",
        "http://127.0.0.1, http://127.0.0.1/v1/",
        "http://127.0.0.1/v1/, http://127.0.0.1/v1/"
    })
    void permitsLocalHttp(String raw, String expected) {
        assertEquals(expected, LiteLlmClient.normalizeBaseUrl(raw).toString());
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "example.com",
        "https://example.com/api",
        "https://example.com/v2",
        "http://example.com",
        "ftp://example.com"
    })
    void rejectsUnexpectedOrInsecureUrls(String raw) {
        assertThrows(IllegalArgumentException.class, () -> LiteLlmClient.normalizeBaseUrl(raw));
    }
}
