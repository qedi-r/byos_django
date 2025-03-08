import base64
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from trmnl import plugins
from trmnl.plugin.homeassistant import HomeAssistantPlugin

from .middleware import require_api_key
from .models import Device, Screen


def index(request):
    return redirect("admin:index")


def setup(request):
    # get mac from headers
    mac = request.headers.get("ID", None)
    if not mac:
        return JsonResponse(
            {
                "status": 404,
                "api_key": None,
                "friendly_id": None,
                "image_url": None,
                "message": "ID header is required.",
            },
            status=200,
        )
    # get device from database
    device = Device.objects.filter(mac_address=mac).first()
    if device:
        if device.user:
            # already set up, act as if we don't exist
            return JsonResponse(
                {
                    "status": 404,
                    "api_key": None,
                    "friendly_id": None,
                    "image_url": None,
                    "filename": None,
                },
                status=200,
            )
        else:
            return JsonResponse(
                {
                    "status": 200,
                    "api_key": device.api_key,
                    "friendly_id": device.friendly_id,
                    "image_url": None,
                    "filename": None,
                    "message": f"Device {device.friendly_id} added to BYOS! Please log in to attach it to a user to continue.",
                },
                status=200,
            )

    device = Device.objects.create(mac_address=mac, device_name="A TRMNL Device")
    return JsonResponse(
        {
            "status": 200,
            "api_key": device.api_key,
            "friendly_id": device.friendly_id,
            "image_url": None,
            "filename": None,
            "message": f"Device {device.friendly_id} added to BYOS! Please log in to attach it to a user to continue.",
        },
        status=200,
    )


def display(request):
    # get mac from headers
    api_key = request.headers.get("Access-Token", None)
    mac = request.headers.get("ID", None)
    if not api_key or not mac:
        return JsonResponse(
            {
                "status": 500,
                "reset_firmware": True,
                "message": "Device not found",
            },
            status=200,
        )
    # get device from database
    device = Device.objects.filter(api_key=api_key, mac_address=mac).first()
    if not device:
        return JsonResponse(
            {
                "status": 500,
                "reset_firmware": True,
                "message": "Device not found",
            },
            status=200,
        )

    if not device.user:
        return JsonResponse(
            {
                "status": 202,
                "image_url": "https://usetrmnl.com/images/setup/setup-logo.bmp",
                "filename": "setup-logo.bmp",
                "refresh_rate": "30",
                "reset_firmware": False,
                "update_firmware": False,
                "firmware_url": None,
                "special_function": "none",
                "message": f"Device {device.friendly_id} added to BYOS! Please log in to attach it to a user to continue.",
            },
            status=200,
        )

    # get latest screen, or rover if no screen
    screen = device.get_screen(update_last_seen=True)
    if not screen:
        image_url = request.build_absolute_uri("/static/images/rover.bmp")
        filename = "rover.bmp"
    elif request.GET.get("base64"):
        image_url = screen.image_as_base64
        filename = screen.image_as_url_for_device_filename
    else:
        image_url = request.build_absolute_uri(screen.image_as_url_for_device)
        filename = screen.image_as_url_for_device_filename

    return JsonResponse(
        {
            "status": 0,
            "image_url": image_url,
            "filename": filename,
            "refresh_rate": f"{device.refresh_rate}",
            "reset_firmware": False,
            "update_firmware": False,
            "firmware_url": None,
            "special_function": "none",
        },
        status=200,
    )


@csrf_exempt
def log(request):
    # get Acesss-Token
    api_key = request.headers.get("Access-Token", None)
    if not api_key:
        return JsonResponse(
            {
                "status": 500,
                "message": "Device not found",
            },
            status=500,
        )
    # get device from database
    device = Device.objects.filter(api_key=api_key).first()
    if not device:
        return JsonResponse(
            {
                "status": 500,
                "message": "Device not found",
            },
            status=500,
        )

    try:
        message = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        message = request.body.decode("utf-8")

    device.devicelog_set.create(message=message)

    return JsonResponse(
        {
            "status": 200,
            "message": "Log received",
        },
        status=200,
    )


def device_image_view(request, filename):
    device_id, screen_id = filename.replace(".bmp", "").split("-")
    # get api_key from params
    api_key = request.GET.get("api_key", None)
    if not api_key:
        return JsonResponse(
            {
                "status": 404,
                "message": "Screen not found",
            },
            status=404,
        )

    screen = Screen.objects.filter(device__friendly_id=device_id, id=screen_id).first()
    if not screen or screen.device.api_key != api_key:
        return JsonResponse(
            {
                "status": 404,
                "message": "Screen not found",
            },
            status=404,
        )

    return HttpResponse(screen.screen, content_type="image/bmp")


@csrf_exempt
@require_api_key
def generate_screen(request):
    # get JSON body
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": 400,
                "message": "Invalid request",
            },
            status=400,
        )

    device = Device.objects.filter(
        user=request.api_key.user, friendly_id=data["device"].upper()
    ).first()
    if not device:
        return JsonResponse(
            {
                "status": 404,
                "message": "Device not found",
            },
            status=404,
        )

    screen = device.screen_set.create(
        html=data["html"],
    )

    try:
        screen.generate_screen()
        return JsonResponse(
            {
                "status": 200,
                "message": "Screenshot created",
                "image": screen.image_as_base64,
            },
            status=200,
        )
    except Exception as e:
        return JsonResponse(
            {
                "status": 500,
                "message": f"Error creating screenshot: {e}",
            },
            status=500,
        )


def generate_html_for_plugin(plugin_name):
    if plugin_name == "ha":
        plugin = HomeAssistantPlugin(config={})
        return plugin.generate_html()


@csrf_exempt
@require_api_key
def generate_plugin(request):
    # get JSON body
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": 400,
                "message": "Invalid request",
            },
            status=400,
        )

    device = Device.objects.filter(
        user=request.api_key.user, friendly_id=data["device"].upper()
    ).first()
    if not device:
        return JsonResponse(
            {
                "status": 404,
                "message": "Device not found",
            },
            status=404,
        )

    generated_data = generate_html_for_plugin(data["plugin"].lower())
    screen = device.screen_set.create(html=generated_data)

    try:
        screen.generate_screen()
        return JsonResponse(
            {
                "status": 200,
                "message": "Screenshot created",
                "image": screen.image_as_base64,
            },
            status=200,
        )
    except Exception as e:
        return JsonResponse(
            {
                "status": 500,
                "message": f"Error creating screenshot: {e}",
            },
            status=500,
        )


@login_required(login_url="/admin/login/")
def preview(request):
    return render(
        request,
        "live_preview.html",
        {
            "initial_content": base64.b64encode(
                open("templates/base.html").read().encode()
            ).decode()
        },
    )


@login_required(login_url="/admin/login/")
def plugin_preview(request):
    return render(
        request,
        "live_preview.html",
        {"plugin_name": "ha"},
    )
