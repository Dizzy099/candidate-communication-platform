from django.contrib import admin

from .models import Candidate


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["candidate_code", "full_name", "phone", "email", "created_at"]
    search_fields = ["full_name", "phone", "email", "candidate_code"]
