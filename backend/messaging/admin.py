from django.contrib import admin

from .models import Message, MessageAttempt, MessageBatch, MessageEvent, MessageTemplate


class AttemptInline(admin.TabularInline):
    model = MessageAttempt
    extra = 0
    readonly_fields = [f.name for f in MessageAttempt._meta.fields]


class EventInline(admin.TabularInline):
    model = MessageEvent
    extra = 0
    readonly_fields = [f.name for f in MessageEvent._meta.fields]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "candidate", "status", "error_category", "attempt_count", "created_at"]
    list_filter = ["status", "error_category", "provider"]
    inlines = [AttemptInline, EventInline]


admin.site.register(MessageBatch)
admin.site.register(MessageTemplate)
