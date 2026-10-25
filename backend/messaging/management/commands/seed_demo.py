"""Load fictional demo data.

    python manage.py seed_demo           # only if the database is empty
    python manage.py seed_demo --reset   # wipe candidates/messages/templates first

All people are fictional; emails use the reserved example.com domain. Seeded
message history is marked as demo history: it was never sent through the
provider. Phone numbers ending in 000/111/.../777 trigger the simulator's
failure scenarios (see README).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from candidates.models import Candidate
from messaging.models import (
    ErrorCategory,
    EventKind,
    EventSource,
    Message,
    MessageBatch,
    MessageEvent,
    MessageStatus,
    MessageTemplate,
)

# (name, phone, email local part, candidate code, history)
# history items: (days_ago, hh:mm, status, body)
CANDIDATES = [
    ("Krishna Khandelwal", "+919876543210", "krishna.khandelwal", "A1B2C3", [
        (3, "10:47", "read", "Hi Krishna, thanks for applying! We loved your portfolio and "
                             "would like to schedule a call this week."),
        (37, "22:00", "read", "Hi Krishna, a reminder that the online assessment closes on Friday."),
        (44, "22:00", "read", "Welcome to our hiring process, Krishna! We'll keep you updated here."),
    ]),
    ("Urvashi Soni", "+919123456789", "urvashi.soni", "D4E5F6", [
        (11, "09:15", "failed", "Hi Urvashi, your interview is scheduled for tomorrow at 11:00 AM."),
        (20, "16:30", "read", "Welcome to our hiring process, Urvashi!"),
    ]),
    ("Aditya Kumar", "+919988766554", "aditya.kumar", "G7H8I9", [
        (8, "11:05", "read", "Hi Aditya, please share two slots for a technical interview next week."),
    ]),
    ("Ajit Srivastava", "+919234567890", "ajit.srivastava", "J1K2L3", [
        (5, "14:20", "read", "Hi Ajit, congratulations on clearing the first round!"),
    ]),
    ("Aniket Sawant", "+919876512345", "aniket.sawant", "M4N5O6", [
        (2, "09:47", "sent", "Hi Aniket, your offer letter has been emailed to you."),
    ]),
    ("Ira Akbar", "+919456789012", "ira.akbar", "P7Q8R9", []),
    ("Amarjeet Kumar", "+919012345678", "amarjeet.kumar", "S1T2U3", []),
    ("Rahul Sharma", "+919811122334", "rahul.sharma", "B2C3D4", [
        (1, "18:10", "delivered", "Hi Rahul, your interview is scheduled for tomorrow at 11:00 AM."),
    ]),
    ("Priya Shah", "+919822233445", "priya.shah", "C3D4E5", []),
    ("Amit Kumar", "+919833344556", "amit.kumar", "E5F6G7", []),
    ("Neha Patel", "+919844455667", "neha.patel", "F6G7H8", []),
    ("Rohan Mehta", "+919855566778", "rohan.mehta", "H8I9J1", []),
    ("Sneha Kulkarni", "+919866677889", "sneha.kulkarni", "K2L3M4", []),
    ("Deepa Kumar", "+919930074333", "deepa.kumar", "L3M4N5", []),       # 333: delivery fails first time
    ("Rohit Deshmukh", "+919820041000", "rohit.deshmukh", "N5O6P7", []),  # 000: invalid recipient
    ("Neha Joshi", "+919811152111", "neha.joshi", "Q8R9S1", []),          # 111: temporary error once
    ("Siddharth Patil", "+919700063222", "siddharth.patil", "T2U3V4", []),  # 222: rate limited once
    ("Kavya Menon", "+919845085444", "kavya.menon", "W5X6Y7", []),        # 444: delivered, never read
    ("Arjun Nair", "+919886096555", "arjun.nair", "Z8A9B1", []),          # 555: duplicate/out-of-order events
    ("Pooja Iyer", "+919900017666", "pooja.iyer", "C2D3E4", []),          # 666: needs a manual retry
    ("Vikram Rao", "+919849028777", "vikram.rao", "F5G6H7", []),          # 777: always fails temporarily
]

TEMPLATES = [
    ("Interview reminder", "Hi {{first_name}}, your interview is scheduled for tomorrow at 11:00 AM. "
                           "Reply here if you need to reschedule."),
    ("Welcome", "Welcome to our hiring process, {{first_name}}! We'll keep you updated here."),
    ("Document request", "Hi {{first_name}}, please email your updated resume and quote your candidate "
                         "ID {{candidate_id}}."),
]

DEMO_NOTE = "Demo history (seeded; not sent through the provider)."


class Command(BaseCommand):
    help = "Load fictional demo candidates, message history and templates."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing candidates, messages and templates first.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            MessageBatch.objects.all().delete()
            Candidate.objects.all().delete()
            MessageTemplate.objects.all().delete()
            MessageEvent.objects.filter(message__isnull=True).delete()
        elif Candidate.objects.exists():
            raise CommandError("The database already has candidates. Use --reset to replace them with demo data.")

        now = timezone.now()
        for index, (name, phone, email, code, history) in enumerate(CANDIDATES):
            candidate = Candidate(full_name=name, phone=phone, email=f"{email}@example.com", candidate_code=code)
            candidate.save()
            # Keep the design's order: earlier rows were added more recently.
            Candidate.objects.filter(pk=candidate.pk).update(created_at=now - timedelta(days=60, minutes=index))
            for days_ago, hhmm, status, body in history:
                self._seed_message(candidate, now, days_ago, hhmm, status, body)

        for name, body in TEMPLATES:
            MessageTemplate.objects.create(name=name, body=body)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(CANDIDATES)} candidates, {Message.objects.count()} messages and {len(TEMPLATES)} templates."
        ))

    def _seed_message(self, candidate, now, days_ago, hhmm, status, body):
        hour, minute = map(int, hhmm.split(":"))
        local_now = timezone.localtime(now)
        created = (local_now - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        message = Message.objects.create(
            candidate=candidate, body=body, provider="simulator", status=status,
            idempotency_key=f"seed_{candidate.candidate_code}_{days_ago}",
            provider_message_id=f"seed_{candidate.candidate_code}_{days_ago}",
            attempt_count=1, max_attempts=5,
        )
        fields = {"created_at": created, "sent_at": created}
        if status in ("delivered", "read"):
            fields["delivered_at"] = created + timedelta(seconds=40)
        if status == "read":
            fields["read_at"] = created + timedelta(minutes=12)
        if status == "failed":
            fields.update(
                failed_at=created + timedelta(minutes=1),
                error_category=ErrorCategory.DELIVERY_FAILED,
                error_code="undeliverable",
                error_detail="Handset unreachable.",
            )
        Message.objects.filter(pk=message.pk).update(**fields)
        MessageEvent.objects.create(
            message=message, source=EventSource.SYSTEM, kind=EventKind.STATUS_CHANGED,
            status=MessageStatus(status), detail=DEMO_NOTE, occurred_at=created,
        )
