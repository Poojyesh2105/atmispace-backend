from django.core.cache import cache
from django.utils import timezone


class MetricsService:
    API_METRIC_TTL_SECONDS = 60 * 60 * 24 * 14

    @staticmethod
    def _key(*parts):
        return ":".join(str(part) for part in parts if part is not None and part != "")

    @staticmethod
    def _increment(key, amount=1, timeout=None):
        added = cache.add(key, 0, timeout=timeout or MetricsService.API_METRIC_TTL_SECONDS)
        if added:
            cache.incr(key, amount)
        else:
            try:
                cache.incr(key, amount)
            except ValueError:
                cache.set(key, amount, timeout=timeout or MetricsService.API_METRIC_TTL_SECONDS)

    @staticmethod
    def record_api_request(*, module, action, status_code, duration_ms, organization_id=None):
        day = timezone.localdate().isoformat()
        status_family = f"{int(status_code) // 100}xx"
        request_key = MetricsService._key("metrics", "api", day, organization_id or "global", module, action, "requests")
        status_key = MetricsService._key("metrics", "api", day, organization_id or "global", module, action, status_family)
        latency_total_key = MetricsService._key("metrics", "api", day, organization_id or "global", module, action, "latency_total_ms")
        latency_max_key = MetricsService._key("metrics", "api", day, organization_id or "global", module, action, "latency_max_ms")

        MetricsService._increment(request_key)
        MetricsService._increment(status_key)
        MetricsService._increment(latency_total_key, amount=max(int(duration_ms), 0))

        current_max = cache.get(latency_max_key, 0)
        if int(duration_ms) > int(current_max or 0):
            cache.set(latency_max_key, int(duration_ms), timeout=MetricsService.API_METRIC_TTL_SECONDS)

