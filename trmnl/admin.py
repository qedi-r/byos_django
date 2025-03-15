import json

from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from .models import (
    APIKey,
    Device,
    DeviceLog,
    Schedule,
    ScheduleDeviceMapping,
    ScheduleEvent,
    Screen,
)


class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "friendly_id",
        "device_name",
        "user",
        "refresh_rate",
        "last_seen_at",
    )
    list_filter = ("user", "created_at")
    search_fields = ("friendly_id", "device_name", "mac_address")
    list_editable = ("device_name", "user", "refresh_rate")

    def has_add_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Make all fields read-only except device_name and user
        editable_fields = {"device_name", "user", "refresh_rate", "timezone"}
        all_fields = {field.name for field in self.model._meta.fields}
        readonly_fields = all_fields - editable_fields
        return readonly_fields


class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("name",)


class ScheduleDeviceMappingAdmin(admin.ModelAdmin):
    list_display = ("device", "schedule")


class ScheduleEventAdmin(admin.ModelAdmin):
    list_display = ("schedule", "start_time", "end_time")
    list_filter = ("schedule",)


class DeviceLogAdmin(admin.ModelAdmin):
    list_display = ("device", "created_at")
    list_filter = ("device", "created_at")
    search_fields = ("device", "message")
    readonly_fields = ("device", "created_at", "message_pretty")
    fields = ("device", "created_at", "message_pretty")

    def message_pretty(self, obj=None):
        result = ""
        if obj and obj.message:
            result = json.dumps(obj.message, indent=4, sort_keys=True)
            # keep spaces
            result_str = f"<pre>{result}</pre>"
            result = mark_safe(result_str)
        return result

    message_pretty.short_description = "Message"


class ScreenAdmin(admin.ModelAdmin):
    list_display = ("device", "created_at", "generated")
    list_filter = ("device", "created_at", "generated")
    search_fields = ("device", "html")
    readonly_fields = ("created_at", "generated", "embed_image")
    fields = ("device", "created_at", "generated", "html", "embed_image")
    actions = ["generate"]

    def embed_image(self, obj=None):
        result = ""
        if obj and obj.generated:
            result = f'<img src="{obj.image_as_base64}" alt="screen">'
        return mark_safe(result)

    embed_image.short_description = "Generated Image"

    def get_readonly_fields(self, request, obj=...):
        if obj and obj.generated:
            return ["created_at", "generated", "html", "embed_image"]
        return ["created_at", "generated", "embed_image"]

    def generate(self, request, queryset):
        objs = queryset.filter(generated=False)
        obj: Screen
        for obj in objs:
            obj.generate_screen()

    def save_model(self, request, obj, form, change):
        if not obj.generated:
            obj.generate_screen()
        super().save_model(request, obj, form, change)


class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "created_at")
    list_filter = ("user", "created_at")
    search_fields = ("name", "user__username")
    exclude = ("key",)

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.save()
            # show message with key
            self.message_user(
                request,
                f"Your API Key is {obj.key}. It will not be shown again.",
                level=messages.SUCCESS,
            )
        super().save_model(request, obj, form, change)


admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceLog, DeviceLogAdmin)
admin.site.register(Screen, ScreenAdmin)
admin.site.register(APIKey, APIKeyAdmin)
admin.site.register(Schedule, ScheduleAdmin)
admin.site.register(ScheduleEvent, ScheduleEventAdmin)
admin.site.register(ScheduleDeviceMapping, ScheduleDeviceMappingAdmin)
