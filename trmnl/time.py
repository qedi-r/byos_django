from datetime import datetime, time, timedelta
import pytz


def default_timezone():
    return pytz.timezone(datetime.now().astimezone().tzname())


def current_time(timezone):
    timezone = default_timezone() if timezone == None else timezone
    return datetime.now().astimezone(pytz.timezone(timezone)).time()


def seconds_until(target_time: time, timezone: str):
    tz = pytz.timezone(timezone)
    now = datetime.now().astimezone(tz)
    target_datetime = datetime.combine(now.date(), target_time, tzinfo=now.tzinfo)
    if target_datetime < now:
        return 0
    difference = target_datetime - now
    return difference.seconds


def server_time():
    return datetime.now()


def is_hour(checked_datetime, hour, tz=None):
    if not checked_datetime:
        return False
    if tz == None:
        tz = default_timezone()

    return datetime.fromisoformat(checked_datetime).astimezone(tz).hour == hour
