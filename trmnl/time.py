from datetime import datetime, time, timedelta
import pytz


def default_timezone():
    return pytz.timezone(datetime.now().astimezone().tzname())


def current_time(timezone: str):
    timezone = default_timezone() if timezone == None else pytz.timezone(timezone)
    return datetime.now().astimezone(timezone).time()


def str_to_date(date_str: str):
    return datetime.fromisoformat(date_str)


def seconds_until_datetime(target_time: datetime):
    now = datetime.now().astimezone(target_time.tzinfo)
    return seconds_diff(target_time, now)


def seconds_until_next_time(target_time: time, timezone: str):
    tz = pytz.timezone(timezone)
    now = datetime.now().astimezone(tz)
    target_datetime = datetime.combine(now.date(), target_time, tzinfo=now.tzinfo)
    return seconds_diff(target_datetime, now)


def seconds_diff(target_datetime, now):
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
