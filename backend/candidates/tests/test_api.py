import re
from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from candidates.models import Candidate
from core.testing import ApiTestCase, make_candidate
from messaging.models import Message, MessageStatus

URL = "/api/candidates"


def add_message(candidate, status=MessageStatus.SENT, minutes_ago=0):
    message = Message.objects.create(
        candidate=candidate, body="Hello", provider="fake", status=status, idempotency_key=f"k-{Message.objects.count()}"
    )
    Message.objects.filter(pk=message.pk).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
    return message


class CreateCandidateTests(ApiTestCase):
    def test_creates_candidate_with_normalised_contact_details(self):
        response = self.client.post(URL, {"full_name": " Priya  Shah ", "phone": "098765 43210",
                                          "email": "Priya.Shah@Example.com"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        body = response.json()
        self.assertEqual(body["full_name"], "Priya Shah")
        self.assertEqual(body["phone"], "+919876543210")
        self.assertEqual(body["phone_display"], "+91 9876543210")
        self.assertEqual(body["email"], "priya.shah@example.com")
        self.assertRegex(body["candidate_code"], r"^[A-Z]\d[A-Z]\d[A-Z]\d$")
        self.assertIsNone(body["last_message"])
        self.assertTrue(Candidate.objects.filter(phone="+919876543210").exists())

    def test_missing_fields_return_friendly_field_errors(self):
        response = self.client.post(URL, {}, format="json")
        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(error["code"], "validation_error")
        self.assertEqual(set(error["fields"]), {"full_name", "phone", "email"})
        self.assertIn("mobile number", error["fields"]["phone"])

    def test_invalid_phone_and_email_are_rejected(self):
        response = self.client.post(URL, {"full_name": "Priya Shah", "phone": "12345", "email": "nope"}, format="json")
        self.assertEqual(response.status_code, 400)
        fields = response.json()["error"]["fields"]
        self.assertIn("10-digit Indian mobile", fields["phone"])
        self.assertIn("valid email", fields["email"])
        self.assertEqual(Candidate.objects.count(), 0)

    def test_duplicate_phone_in_another_format_is_rejected_with_existing_name(self):
        existing = make_candidate("Krishna Khandelwal", "+919876543210")
        response = self.client.post(URL, {"full_name": "Someone Else", "phone": "98765-43210",
                                          "email": "else@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        message = response.json()["error"]["fields"]["phone"]
        self.assertIn("Krishna Khandelwal", message)
        self.assertIn(existing.candidate_code, message)

    def test_duplicate_email_is_case_insensitive(self):
        make_candidate("Krishna Khandelwal", "+919876543210", "krishna@example.com")
        response = self.client.post(URL, {"full_name": "Other Person", "phone": "9123456789",
                                          "email": "KRISHNA@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["error"]["fields"])


class ListCandidatesTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.krishna = make_candidate("Krishna Khandelwal", "+919876543210")
        self.urvashi = make_candidate("Urvashi Soni", "+919123456789")
        self.ira = make_candidate("Ira Akbar", "+919456789012")
        add_message(self.krishna, MessageStatus.READ, minutes_ago=30)
        add_message(self.krishna, MessageStatus.SENT, minutes_ago=5)
        add_message(self.urvashi, MessageStatus.FAILED, minutes_ago=10)

    def names(self, response):
        return [c["full_name"] for c in response.json()["results"]]

    def test_lists_newest_first_with_latest_message_status(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)
        self.assertEqual(self.names(response), ["Ira Akbar", "Urvashi Soni", "Krishna Khandelwal"])
        by_name = {c["full_name"]: c for c in response.json()["results"]}
        self.assertEqual(by_name["Krishna Khandelwal"]["last_message"]["status"], "sent")
        self.assertEqual(by_name["Urvashi Soni"]["last_message"]["status_label"], "Failed")
        self.assertIsNone(by_name["Ira Akbar"]["last_message"])

    def test_list_query_count_does_not_grow_with_rows(self):
        for i in range(10):
            add_message(make_candidate(f"Extra Person {chr(65 + i)}", f"+91990000000{i}"))
        with CaptureQueriesContext(connection) as queries:
            self.client.get(URL, {"page_size": 50})
        self.assertLessEqual(len(queries), 3)  # count + page (+ savepoint noise)

    def test_search_matches_name_phone_email_and_code(self):
        cases = {
            "urvashi": ["Urvashi Soni"],
            "98765 43210": ["Krishna Khandelwal"],
            "+91 94567": ["Ira Akbar"],
            "ira.akbar@": ["Ira Akbar"],
            self.krishna.candidate_code.lower(): ["Krishna Khandelwal"],
            "nobody": [],
        }
        for term, expected in cases.items():
            with self.subTest(term=term):
                self.assertEqual(self.names(self.client.get(URL, {"search": term})), expected)

    def test_filter_by_last_message_status(self):
        self.assertEqual(self.names(self.client.get(URL, {"status": "failed"})), ["Urvashi Soni"])
        self.assertEqual(self.names(self.client.get(URL, {"status": "none"})), ["Ira Akbar"])

    def test_ordering_by_last_message_puts_never_messaged_last(self):
        response = self.client.get(URL, {"ordering": "-last_message_at"})
        self.assertEqual(self.names(response), ["Krishna Khandelwal", "Urvashi Soni", "Ira Akbar"])

    def test_pagination(self):
        response = self.client.get(URL, {"page_size": 2, "page": 2})
        self.assertEqual(response.json()["count"], 3)
        self.assertEqual(len(response.json()["results"]), 1)


class DetailAndDeleteTests(ApiTestCase):
    def test_retrieve_and_not_found_shape(self):
        candidate = make_candidate()
        self.assertEqual(self.client.get(f"{URL}/{candidate.pk}").json()["full_name"], "Asha Verma")
        response = self.client.get(f"{URL}/99999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_delete_removes_candidate_and_history(self):
        candidate = make_candidate()
        add_message(candidate)
        response = self.client.delete(f"{URL}/{candidate.pk}")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Candidate.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_bulk_delete_reports_missing_ids(self):
        a = make_candidate("Asha Verma", "+919800000001")
        b = make_candidate("Bina Rao", "+919800000002")
        keep = make_candidate("Chetan Das", "+919800000003")
        response = self.client.post(f"{URL}/bulk-delete", {"ids": [a.pk, b.pk, 4242]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": 2, "not_found": [4242]})
        self.assertEqual(list(Candidate.objects.values_list("pk", flat=True)), [keep.pk])

    def test_bulk_delete_requires_ids(self):
        response = self.client.post(f"{URL}/bulk-delete", {"ids": []}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_trailing_slash_is_optional(self):
        self.assertEqual(self.client.get(f"{URL}/").status_code, 200)
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_candidate_code_format(self):
        self.assertTrue(re.match(r"^[A-Z]\d[A-Z]\d[A-Z]\d$", make_candidate().candidate_code))
