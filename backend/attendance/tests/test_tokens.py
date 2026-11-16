"""Unit tests for the rotating QR token logic (no Django required)."""
import unittest

from attendance.services import tokens

SECRET = "a" * 64
INTERVAL = 30
T0 = 1_800_000_000.0  # arbitrary fixed "server time"


class TokenTests(unittest.TestCase):
    def test_round_trip(self):
        token = tokens.make_token(SECRET, 7, INTERVAL, now=T0)
        parsed = tokens.parse_token(token)
        self.assertEqual(parsed.session_id, 7)
        tokens.verify_token(SECRET, parsed, INTERVAL, grace_windows=1, now=T0 + 5)

    def test_token_is_stable_inside_a_window_and_changes_after(self):
        window_start = (int(T0) // INTERVAL) * INTERVAL
        a = tokens.make_token(SECRET, 7, INTERVAL, now=window_start + 1)
        b = tokens.make_token(SECRET, 7, INTERVAL, now=window_start + INTERVAL - 1)
        c = tokens.make_token(SECRET, 7, INTERVAL, now=window_start + INTERVAL + 1)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_previous_window_accepted_within_grace(self):
        token = tokens.make_token(SECRET, 7, INTERVAL, now=T0)
        parsed = tokens.parse_token(token)
        tokens.verify_token(SECRET, parsed, INTERVAL, grace_windows=1, now=T0 + INTERVAL)

    def test_old_token_expires(self):
        token = tokens.make_token(SECRET, 7, INTERVAL, now=T0)
        parsed = tokens.parse_token(token)
        with self.assertRaises(tokens.ExpiredToken):
            tokens.verify_token(SECRET, parsed, INTERVAL, grace_windows=1, now=T0 + 3 * INTERVAL)

    def test_zero_grace_rejects_previous_window(self):
        window_start = (int(T0) // INTERVAL) * INTERVAL
        token = tokens.make_token(SECRET, 7, INTERVAL, now=window_start + 1)
        parsed = tokens.parse_token(token)
        with self.assertRaises(tokens.ExpiredToken):
            tokens.verify_token(SECRET, parsed, INTERVAL, grace_windows=0, now=window_start + INTERVAL + 1)

    def test_wrong_secret_rejected(self):
        token = tokens.make_token(SECRET, 7, INTERVAL, now=T0)
        parsed = tokens.parse_token(token)
        with self.assertRaises(tokens.InvalidSignature):
            tokens.verify_token("b" * 64, parsed, INTERVAL, now=T0)

    def test_tampered_session_id_rejected(self):
        token = tokens.make_token(SECRET, 7, INTERVAL, now=T0)
        _, window, signature = token.split(".")
        parsed = tokens.parse_token(f"8.{window}.{signature}")
        with self.assertRaises(tokens.InvalidSignature):
            tokens.verify_token(SECRET, parsed, INTERVAL, now=T0)

    def test_tampered_window_rejected(self):
        token = tokens.make_token(SECRET, 7, INTERVAL, now=T0)
        session_id, window, signature = token.split(".")
        parsed = tokens.parse_token(f"{session_id}.{int(window) + 1}.{signature}")
        with self.assertRaises(tokens.InvalidSignature):
            tokens.verify_token(SECRET, parsed, INTERVAL, now=T0)

    def test_future_window_rejected(self):
        future = tokens.make_token(SECRET, 7, INTERVAL, now=T0 + 10 * INTERVAL)
        parsed = tokens.parse_token(future)
        with self.assertRaises(tokens.TokenError):
            tokens.verify_token(SECRET, parsed, INTERVAL, now=T0)

    def test_malformed_tokens(self):
        bad = [
            "",
            "abc",
            "1.2",
            "1.2.3.4",
            "x.2." + "a" * 24,
            "1.y." + "a" * 24,
            "1.2." + "g" * 24,  # not hexadecimal
            "1.2." + "a" * 23,  # too short
            "1.2." + "A" * 24,  # upper case is not produced by the server
            "²1.2." + "a" * 24,  # unicode digit
            "1." + "2" * 200 + "." + "a" * 24,  # too long
            None,
            12345,
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(tokens.MalformedToken):
                    tokens.parse_token(value)

    def test_seconds_until_rotation(self):
        self.assertAlmostEqual(tokens.seconds_until_rotation(30, now=60.0), 30.0)
        self.assertAlmostEqual(tokens.seconds_until_rotation(30, now=75.0), 15.0)

    def test_secrets_are_unique_and_long(self):
        first, second = tokens.new_secret(), tokens.new_secret()
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
