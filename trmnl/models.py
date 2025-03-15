import base64
import json
import logging
import random
import re
import shutil
import string
import tempfile

import pytz
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from playwright.sync_api import sync_playwright
from wand.image import Image

from trmnl.time import current_time, server_time

log = logging.getLogger(__name__)


def timezone_choices():
    return list(map(lambda tz: (tz, tz), pytz.common_timezones))


class Device(models.Model):
    friendly_id = models.CharField(max_length=6, unique=True, null=False, blank=False)
    device_name = models.CharField(max_length=50)
    mac_address = models.CharField(max_length=17, unique=True, null=False, blank=False)
    api_key = models.CharField(max_length=32, unique=True, null=False, blank=False)
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)
    updated_at = models.DateTimeField(auto_now=True, null=False, blank=False)
    last_seen_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    refreshes = models.IntegerField(default=0)
    refresh_rate = models.IntegerField(default=900)
    timezone = models.CharField(max_length=64, choices=timezone_choices, null=True)

    def __str__(self):
        return f"{self.device_name} ({self.friendly_id})"

    def clean(self):
        # Validate MAC Address format
        self.mac_address = self.mac_address.upper()
        if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", self.mac_address):
            raise ValidationError({"mac_address": "Invalid MAC address format."})

    def save(self, *args, **kwargs):
        # Generate a random API key on first create
        if not self.mac_address:
            # refuse to save the model if the MAC address is missing
            raise ValidationError({"mac_address": "MAC address is required."})
        if not self.api_key:
            self.api_key = "".join(random.choices(string.ascii_letters, k=32))
        # Generate a random friendly ID on first create
        if not self.friendly_id:
            self.friendly_id = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )

        self.clean()

        super().save(*args, **kwargs)

    def update_last_seen(self):
        self.last_seen_at = server_time()
        self.refreshes += 1
        self.save()

    def get_screen(self, update_last_seen=False):
        screen = self.screen_set.order_by("-created_at").first()
        self.update_last_seen() if update_last_seen else None

        if screen:
            return screen

        return None

    def active_schedule(self):
        return ScheduleDeviceMapping.objects.filter(device=self).first().schedule

    def _get_next_plugin_for_list(self, plugins):
        plugins_obj = json.loads(plugins)
        if len(plugins) > 1:
            last_plugin = self.get_screen().plugin
            if last_plugin and last_plugin in plugins_obj:
                plugin_idx = (plugins_obj.index(last_plugin) + 1) % len(plugins_obj)
                return plugins_obj[plugin_idx]

        return plugins_obj[0]

    def current_scheduled_screen(self):
        return self.active_schedule().current(self.timezone)

    def next_scheduled_screen(self):
        return self.active_schedule().next(self.timezone)

    def get_scheduled_screen(self, update_last_seen=False):
        plugins = self.current_schedule().plugins
        screen = None
        try:
            plugin = self._get_next_plugin_for_list(plugins)
            screen = self.generate_screen_for_plugin(plugin)
        except Exception as e:
            log.error("Exception: " + str(e))
            return None
        if update_last_seen:
            self.update_last_seen()
        return screen

    def generate_screen_for_plugin(self, plugin_name):
        from trmnl.plugin.plugin_map import plugin_map

        plugin_name = plugin_name.lower()

        context = {
            "timezone": self.timezone,
        }
        plugin = plugin_map(plugin_name, context)
        if plugin:
            generated_data = plugin.generate_html()
            return self.screen_set.create(html=generated_data, plugin=plugin_name)
        else:
            raise Exception(f"unkown plugin {plugin_name}")


class DeviceLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    message = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)


class Schedule(models.Model):
    name = models.TextField()
    updated_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)
    refresh_rate = models.IntegerField(default=900)

    def __str__(self):
        return f"{self.name}"

    def current(self, timezone):
        local_current_time = current_time(timezone)
        return self.scheduleevent_set.filter(
            start_time__lt=local_current_time,
            end_time__gt=local_current_time,
        ).first()

    def next(self, timezone):
        local_current_time = current_time(timezone)
        return (
            self.scheduleevent_set.filter(
                start_time__gt=local_current_time,
            )
            .order_by("start_time")
            .first()
        )


class ScheduleEvent(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()
    plugins = models.TextField()
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)


class ScheduleDeviceMapping(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)


class Screen(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    html = models.TextField()
    screen = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)
    generated = models.BooleanField(default=False)
    plugin = models.TextField(null=True)

    def generate_screen(self):
        # get random file name
        folder = tempfile.mkdtemp()

        with sync_playwright() as p:
            if settings.PW_SERVER:
                browser = p.firefox.connect(ws_endpoint=settings.PW_SERVER)
            else:
                browser = p.firefox.launch(
                    headless=True,
                    args=["--window-size=800,480", "--disable-web-security"],
                )
            page = browser.new_page()
            page.set_viewport_size({"width": 800, "height": 480})

            page.set_content(self.html)
            page.evaluate(
                'document.getElementsByTagName("html")[0].style.overflow = "hidden";'
                'document.getElementsByTagName("body")[0].style.overflow = "hidden";'
            )
            page.screenshot(path=f"/{folder}/screen.png")
            browser.close()

        with Image(filename=f"/{folder}/screen.png") as img:
            img.posterize(2, dither="floyd_steinberg")
            amap = Image(width=img.width, height=img.height, pseudo="pattern:gray50")
            amap.composite(img, 0, 0)
            img = amap
            img.quantize(2, colorspace_type="gray")
            img.depth = 1
            img.strip()
            img.save(filename=f"bmp3:/{folder}/screen.bmp")

        with open(f"/{folder}/screen.bmp", "rb") as f:
            self.screen = f.read()
            self.generated = True
            self.save()

        # clean up
        shutil.rmtree(folder, ignore_errors=True)

    @property
    def image_as_base64(self):
        return f"data:image/bmp;base64,{base64.b64encode(self.screen).decode()}"

    @property
    def image_as_url_for_device(self):
        device_api_key = self.device.api_key
        return f"/api/v1/media/{self.device.friendly_id}-{self.id}.bmp?api_key={device_api_key}"

    @property
    def image_as_url_for_device_filename(self):
        return f"{self.device.friendly_id}-{self.id}.bmp"


class APIKey(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    key = models.CharField(max_length=32, unique=True, null=False, blank=False)
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, null=False, blank=False
    )
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)

    def save(self, *args, **kwargs):
        # Generate a random API key on first create
        if not self.key:
            self.key = "".join(random.choices(string.ascii_letters, k=32))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Owner: {self.user.username})"
