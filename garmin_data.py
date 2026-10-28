"""Shared response policy and tool registry; no network or credentials here."""
import math
import re

TOOL_NAMES = (
    "get_health_summary", "get_recent_activities", "get_data_status",
    "get_sleep_details", "get_health_timeseries", "get_training_metrics",
    "get_activity_details", "get_training_workouts", "get_personal_records",
    "get_device_capabilities",
    "render_garmin_chart",
)


def safe_error(exc):
    """Describe nested failures without exposing response bodies or request URLs."""
    classes, codes, seen, pending = set(), set(), set(), [exc]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        classes.add(type(item).__name__)
        code = getattr(getattr(item, "response", None), "status_code", None)
        if isinstance(code, int):
            codes.add(code)
        pending.extend(getattr(item, "exceptions", ()))
        pending.extend(x for x in (item.__cause__, item.__context__) if x is not None)
    return {"error_types": sorted(classes), "http_statuses": sorted(codes)}

DAILY_FIELDS = (
    "totalSteps", "dailyStepGoal", "totalDistanceMeters", "wellnessDistanceMeters",
    "totalKilocalories", "activeKilocalories", "bmrKilocalories", "wellnessKilocalories",
    "highlyActiveSeconds", "activeSeconds", "sedentarySeconds", "sleepingSeconds",
    "moderateIntensityMinutes", "vigorousIntensityMinutes", "intensityMinutesGoal",
    "floorsAscended", "floorsDescended", "floorsAscendedInMeters", "floorsDescendedInMeters",
    "userFloorsAscendedGoal", "minHeartRate", "maxHeartRate", "restingHeartRate",
    "lastSevenDaysAvgRestingHeartRate", "averageStressLevel", "maxStressLevel",
    "stressDuration", "restStressDuration", "activityStressDuration", "uncategorizedStressDuration",
    "totalStressDuration", "lowStressDuration", "mediumStressDuration", "highStressDuration",
    "stressPercentage", "restStressPercentage", "activityStressPercentage", "uncategorizedStressPercentage",
    "lowStressPercentage", "mediumStressPercentage", "highStressPercentage",
    "bodyBatteryChargedValue", "bodyBatteryDrainedValue", "bodyBatteryHighestValue",
    "bodyBatteryLowestValue", "bodyBatteryMostRecentValue", "bodyBatteryDuringSleep",
    "bodyBatteryAtWakeTime", "averageSpo2", "lowestSpo2", "latestSpo2",
    "avgWakingRespirationValue", "highestRespirationValue", "lowestRespirationValue",
    "latestRespirationValue", "averageMonitoringEnvironmentAltitude",
)

ACTIVITY_FIELDS = (
    "activityId", "activityName", "activityType", "startTimeLocal", "startTimeGMT",
    "distance", "duration", "movingDuration", "elapsedDuration", "averageSpeed", "maxSpeed",
    "averageMovingSpeed", "averageHR", "maxHR", "minHR", "calories", "bmrCalories",
    "elevationGain", "elevationLoss", "maxElevation", "minElevation", "avgElevation",
    "averageRunningCadenceInStepsPerMinute", "maxRunningCadenceInStepsPerMinute",
    "averageRunCadence", "maxRunCadence", "averageBikingCadenceInRevPerMinute",
    "averagePower", "avgPower", "maxPower", "minPower", "normalizedPower", "normPower",
    "totalWork", "groundContactTime", "strideLength", "verticalOscillation", "verticalRatio",
    "trainingEffect", "aerobicTrainingEffect", "anaerobicTrainingEffect", "activityTrainingLoad",
    "trainingEffectLabel", "aerobicTrainingEffectMessage", "anaerobicTrainingEffectMessage",
    "averageTemperature", "maxTemperature", "minTemperature", "waterEstimated",
    "directWorkoutFeel", "directWorkoutRpe", "moderateIntensityMinutes", "vigorousIntensityMinutes",
    "steps", "avgGradeAdjustedSpeed", "differenceBodyBattery", "totalExerciseReps", "activeSets",
    "totalSets", "totalReps", "totalVolume", "minActivityLapDuration", "maxVerticalSpeed",
)

_PRIVATE = re.compile(
    r"(?i)(token|password|secret|authorization|cookie|email|username|displayname|fullname|"
    r"avatar|image|thumbnail|url|serial|owner|userinfo|userprofile|installation|uuid|"
    r"deviceid|userid|profileid|profilepk|userpk|devicepk)"
)
_LOCATION = re.compile(r"(?i)(latitude|longitude|positionlat|positionlong|polyline|location|gps|^(?:lat|lon|lng|startlat|startlon|endlat|endlon)$)")


def clean_data(value, *, allow_location=False, keep_ids=("activityId", "workoutId")):
    """Curate data recursively, stripping account/device identity and credentials."""
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            key = str(key)
            if _PRIVATE.search(key):
                continue
            if not allow_location and _LOCATION.search(key):
                continue
            if key not in keep_ids and (key.lower().endswith(("id", "pk", "ids")) or key == "author"):
                continue
            # Training maps are keyed by device IDs. Keep the records, not those IDs.
            safe_key = f"entry_{len(output) + 1}" if key.isdigit() else key
            output[safe_key] = clean_data(item, allow_location=allow_location, keep_ids=keep_ids)
        return output
    if isinstance(value, list):
        return [clean_data(v, allow_location=allow_location, keep_ids=keep_ids) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def selected(value, keys):
    return clean_data({key: value[key] for key in keys if key in value}) if isinstance(value, dict) else {}


def sampled(values, max_points):
    """Uniformly sample with both endpoints retained; disclose original length."""
    if not isinstance(values, list):
        return {"source_points": 0, "returned_points": 0, "sampled": False, "values": []}
    count = len(values)
    if count > max_points:
        indices = [round(n * (count - 1) / (max_points - 1)) for n in range(max_points)]
        output = [values[i] for i in indices]
    else:
        output = values
    return {"source_points": count, "returned_points": len(output),
            "sampled": count > max_points, "values": output}
