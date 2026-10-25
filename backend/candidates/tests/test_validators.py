from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from candidates.validators import (
    format_phone_display,
    normalize_email,
    normalize_full_name,
    normalize_indian_mobile,
)


class PhoneNormalisationTests(SimpleTestCase):
    def test_accepts_common_formats(self):
        for raw in ["9876543210", "09876543210", "919876543210", "+919876543210",
                    "+91 98765 43210", "+91-98765-43210", "(+91) 98765.43210"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_indian_mobile(raw), "+919876543210")

    def test_rejects_invalid_numbers(self):
        for raw in ["", "12345", "5876543210", "98765432101", "+1 4155552671", "98765abcde", "+91 1234567890"]:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_indian_mobile(raw)

    def test_display_format_matches_design(self):
        self.assertEqual(format_phone_display("+919876543210"), "+91 9876543210")


class NameAndEmailTests(SimpleTestCase):
    def test_name_whitespace_is_collapsed(self):
        self.assertEqual(normalize_full_name("  Priya   Shah "), "Priya Shah")

    def test_name_allows_common_punctuation(self):
        for name in ["D'Souza Ryan", "Anne-Marie Rao", "Dr. K. Iyer", "Zoë Fernandes"]:
            with self.subTest(name=name):
                self.assertEqual(normalize_full_name(name), name)

    def test_name_rejects_digits_and_symbols(self):
        for name in ["A", "R2D2", "<script>", "Priya_Shah", "x" * 101]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                normalize_full_name(name)

    def test_email_is_lowercased(self):
        self.assertEqual(normalize_email("  Priya.Shah@Example.COM "), "priya.shah@example.com")

    def test_email_rejects_invalid(self):
        for email in ["", "priya", "priya@", "@example.com", "priya shah@example.com"]:
            with self.subTest(email=email), self.assertRaises(ValidationError):
                normalize_email(email)
