package example.litellm;

import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class MainTest {

    @Test
    void targetFlagWithoutValueFailsFast() {
        assertThrows(IllegalArgumentException.class, () -> Main.main(new String[] {"--target"}));
    }

    @Test
    void apiFlagWithoutValueFailsFast() {
        assertThrows(IllegalArgumentException.class, () -> Main.main(new String[] {"--api"}));
    }

    @Test
    void deliverableFormatWithoutValueFailsFast() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--target", "relay", "--deliverable-format"}));
    }

    @Test
    void backgroundAndStreamCannotBeCombined() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--background", "--stream", "hello"}));
    }

    @Test
    void streamRequiresRelayTarget() {
        assertThrows(
                IllegalArgumentException.class,
                () -> Main.main(new String[] {"--stream", "hello"}));
    }
}
