from datetime import datetime, timezone, timedelta

# Indian Standard Time (IST) is UTC + 5:30
IST_TZ = timezone(timedelta(hours=5, minutes=30))

def now_ist() -> datetime:
    """Returns current datetime in Indian Standard Time (UTC + 5:30)."""
    return datetime.now(IST_TZ)

def now_ist_str(fmt: str = "%H:%M:%S") -> str:
    """Returns current IST time string."""
    return now_ist().strftime(fmt)

def now_ist_datetime_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Returns current IST datetime string."""
    return now_ist().strftime(fmt)

def now_ist_date_str(fmt: str = "%Y-%m-%d") -> str:
    """Returns current IST date string."""
    return now_ist().strftime(fmt)

def to_ist_time_str(time_str: str) -> str:
    """
    Takes any time string (e.g. '06:57:49' UTC or '12:27:49' IST or '2026-11-16 12:27:49')
    and converts it to a clean IST time string.
    """
    if not time_str:
        return now_ist_str("%H:%M:%S")
    time_str = str(time_str).strip()
    if 'IST' in time_str or 'PM' in time_str or 'AM' in time_str:
        return time_str
    
    # If date and time are space separated, isolate the time part
    clean_time = time_str
    if ' ' in clean_time:
        for p in clean_time.split(' '):
            if ':' in p:
                clean_time = p
                break
                
    parts = clean_time.split(':')
    if len(parts) >= 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            s = parts[2] if len(parts) > 2 else "00"
            # If hour <= 8 during daytime, it was stored in UTC on cloud servers
            if h <= 8:
                total_mins = h * 60 + m + 330  # +5 hours 30 mins
                h = (total_mins // 60) % 24
                m = total_mins % 60
            return f"{h:02d}:{m:02d}:{s}"
        except Exception:
            pass
    return time_str
