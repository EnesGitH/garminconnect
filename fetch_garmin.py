import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError

load_dotenv()

EMAIL = os.getenv("GARMIN_EMAIL")
PASSWORD = os.getenv("GARMIN_PASSWORD")
OUTPUT_FILE = "garmin_daily_report.txt"


def login() -> Garmin:
    if not EMAIL or not PASSWORD:
        print("Error: GARMIN_EMAIL and GARMIN_PASSWORD must be set in .env")
        sys.exit(1)
    try:
        client = Garmin(EMAIL, PASSWORD)
        client.login()
        return client
    except GarminConnectAuthenticationError as e:
        print(f"Login failed: {e}")
        sys.exit(1)


def safe_get(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def format_duration(seconds) -> str:
    if seconds is None:
        return "N/A"
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h {m}m"


def build_report(client: Garmin, target_date: date) -> str:
    d = target_date.isoformat()
    lines = [
        f"Garmin Daily Health Report — {d}",
        "=" * 45,
        "",
    ]

    # --- Steps ---
    steps_data = safe_get(lambda: client.get_steps_data(d))
    if steps_data:
        total_steps = steps_data[-1].get("steps", 0) if isinstance(steps_data, list) else steps_data.get("totalSteps", "N/A")
        step_goal = safe_get(lambda: client.get_daily_summary(d, "steps"), {})
        goal = step_goal.get("dailyStepGoal", "N/A") if isinstance(step_goal, dict) else "N/A"
    else:
        daily = safe_get(lambda: client.get_daily_summary(d, "steps"), {}) or {}
        total_steps = daily.get("totalSteps", "N/A")
        goal = daily.get("dailyStepGoal", "N/A")

    lines += [
        "SCHRITTE",
        f"  Ist:  {total_steps}",
        f"  Ziel: {goal}",
        "",
    ]

    # --- Sleep ---
    sleep = safe_get(lambda: client.get_sleep_data(d), {}) or {}
    daily_sleep = sleep.get("dailySleepDTO", {}) or {}
    lines += [
        "SCHLAF",
        f"  Gesamtdauer: {format_duration(daily_sleep.get('sleepTimeSeconds'))}",
        f"  Schlaf-Score: {daily_sleep.get('sleepScores', {}).get('overall', {}).get('value', 'N/A') if isinstance(daily_sleep.get('sleepScores'), dict) else daily_sleep.get('sleepScores', 'N/A')}",
        f"  Tiefschlaf:   {format_duration(daily_sleep.get('deepSleepSeconds'))}",
        f"  Leichtschlaf: {format_duration(daily_sleep.get('lightSleepSeconds'))}",
        f"  REM-Schlaf:   {format_duration(daily_sleep.get('remSleepSeconds'))}",
        "",
    ]

    # --- Heart Rate ---
    hr = safe_get(lambda: client.get_heart_rates(d), {}) or {}
    lines += [
        "HERZFREQUENZ",
        f"  Ruhepuls:     {hr.get('restingHeartRate', 'N/A')} bpm",
        f"  Durchschnitt: {hr.get('heartRateValues', [None])[-1][1] if hr.get('heartRateValues') else 'N/A'} bpm",
        "",
    ]

    # --- Body Battery ---
    bb_list = safe_get(lambda: client.get_body_battery(d), []) or []
    if bb_list:
        bb_values = [e.get("value") for e in bb_list if e.get("value") is not None]
        bb_high = max(bb_values) if bb_values else "N/A"
        bb_low = min(bb_values) if bb_values else "N/A"
    else:
        bb_high = bb_low = "N/A"
    lines += [
        "BODY BATTERY",
        f"  Höchstwert: {bb_high}",
        f"  Tiefstwert: {bb_low}",
        "",
    ]

    # --- HRV ---
    hrv = safe_get(lambda: client.get_hrv_data(d), {}) or {}
    hrv_summary = hrv.get("hrvSummary", {}) or {}
    lines += [
        "HRV (HERZFREQUENZVARIABILITÄT)",
        f"  Status:      {hrv_summary.get('status', 'N/A')}",
        f"  Letzter Wert:{hrv_summary.get('lastNight', 'N/A')} ms",
        "",
    ]

    # --- Activities ---
    activities = safe_get(lambda: client.get_activities_by_date(d, d), []) or []
    lines.append("AKTIVITÄTEN")
    if activities:
        for act in activities:
            name = act.get("activityName") or act.get("activityType", {}).get("typeKey", "Unbekannt")
            duration = format_duration(act.get("duration"))
            distance_m = act.get("distance")
            distance = f"{distance_m / 1000:.2f} km" if distance_m else "N/A"
            calories = act.get("calories", "N/A")
            lines += [
                f"  • {name}",
                f"    Dauer:     {duration}",
                f"    Distanz:   {distance}",
                f"    Kalorien:  {calories} kcal",
            ]
    else:
        lines.append("  Keine Aktivitäten gefunden.")

    lines.append("")
    return "\n".join(lines)


def main():
    target_date = date.today() - timedelta(days=1)

    print(f"Logging in as {EMAIL} ...")
    client = login()
    print(f"Fetching data for {target_date} ...")
    report = build_report(client, target_date)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report saved to {OUTPUT_FILE}")
    print()
    print(report)


if __name__ == "__main__":
    main()
