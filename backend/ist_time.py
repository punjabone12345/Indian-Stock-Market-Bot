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

# Official NSE Trading Holidays (2026 Calendar)
NSE_HOLIDAYS_2026 = {
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-20": "Id-ul-Fitr",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-27": "Bakri Id",
    "2026-08-15": "Independence Day",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-08": "Diwali Laxmi Pujan",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas"
}

def get_nse_holiday(dt: datetime = None) -> str:
    """Returns holiday name if dt is an official NSE trading holiday, else None."""
    if dt is None:
        dt = now_ist()
    d_str = dt.strftime("%Y-%m-%d")
    return NSE_HOLIDAYS_2026.get(d_str, None)

def is_trading_day(dt: datetime = None) -> bool:
    """Returns True if dt is a normal weekday and not an NSE holiday."""
    if dt is None:
        dt = now_ist()
    if dt.weekday() >= 5:  # Saturday (5) or Sunday (6)
        return False
    return get_nse_holiday(dt) is None

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
