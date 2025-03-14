import datetime
import pytz


def current_timezone():
    return datetime.datetime.now().astimezone().tzname()


def current_time():
    return (
        datetime.datetime.now()
        .astimezone(pytz.timezone(current_timezone()))
        .strftime("%H:%M:%S")
    )


def is_hour(checked_datetime, hour):
    if not checked_datetime:
        return False

    dt = datetime.fromisoformat(checked_datetime).astimezone(current_timezone())
    return dt.hour == hour
