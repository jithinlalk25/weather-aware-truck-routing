import uuid

from django.db import models


class TripPlan(models.Model):
    """One routing request and its analysed result (an immutable snapshot)."""

    class WindMode(models.TextChoices):
        SUSTAINED = "sustained", "Sustained wind"
        GUST = "gust", "Wind gusts"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    origin_label = models.CharField(max_length=200)
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    origin_tz = models.CharField(max_length=64)
    dest_label = models.CharField(max_length=200)
    dest_lat = models.FloatField()
    dest_lon = models.FloatField()
    dest_tz = models.CharField(max_length=64)

    departure_at = models.DateTimeField(help_text="UTC")
    load_lb = models.PositiveIntegerField()
    interval_mi = models.PositiveSmallIntegerField()
    wind_mode = models.CharField(max_length=10, choices=WindMode.choices)
    hos_enabled = models.BooleanField()

    recommended_label = models.CharField(max_length=1)
    recommendation = models.TextField()
    decided_by = models.CharField(max_length=20)
    tradeoff = models.TextField(blank=True)
    why_not = models.JSONField(default=dict, help_text="Route label -> why it ranks lower")
    warnings = models.JSONField(default=list)
    notes = models.JSONField(default=list)
    weather_meta = models.JSONField(default=dict)

    heatmap = models.JSONField(null=True, blank=True)
    heatmap_computed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.origin_label} → {self.dest_label} ({self.departure_at:%Y-%m-%d %H:%M}Z)"


class RouteOption(models.Model):
    plan = models.ForeignKey(TripPlan, related_name="routes", on_delete=models.CASCADE)
    label = models.CharField(max_length=1)
    rank = models.PositiveSmallIntegerField(help_text="1 = recommended")
    source = models.CharField(max_length=10, help_text="tomtom | via")

    distance_m = models.FloatField()
    drive_s = models.FloatField()
    total_s = models.FloatField(help_text="Drive time plus HOS pauses")
    traffic_delay_s = models.FloatField(default=0)
    arrival_at = models.DateTimeField()

    miles_by_level = models.JSONField()
    avg_risk = models.FloatField(null=True)

    path = models.JSONField(help_text="[[lon, lat, dist_m, elapsed_s], ...] simplified")
    checkpoints = models.JSONField()
    rest_stops = models.JSONField(default=list)

    class Meta:
        ordering = ["label"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "label"], name="unique_route_label_per_plan"),
        ]

    def __str__(self) -> str:
        return f"Route {self.label} of {self.plan_id}"
