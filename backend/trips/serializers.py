from rest_framework import serializers

from domain.geo import METERS_PER_MILE
from domain.sampling import ALLOWED_INTERVALS_MI

from .models import RouteOption, TripPlan
from .services.timezones import is_us_location

MAX_LOAD_LB = 80_000


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)

    def validate(self, attrs):
        if not is_us_location(attrs["lat"], attrs["lon"]):
            raise serializers.ValidationError("Only locations in the United States are supported.")
        return attrs


class PlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_local = serializers.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        help_text="Wall-clock time at the origin, without offset (e.g. 2026-10-11T08:00).",
    )
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=ALLOWED_INTERVALS_MI, default=25)
    wind_mode = serializers.ChoiceField(choices=TripPlan.WindMode.choices, default="sustained")
    hos = serializers.BooleanField(default=True)


class RouteOptionSerializer(serializers.ModelSerializer):
    distance_mi = serializers.SerializerMethodField()

    class Meta:
        model = RouteOption
        fields = [
            "label", "rank", "source", "distance_mi", "drive_s", "total_s", "traffic_delay_s",
            "arrival_at", "miles_by_level", "avg_risk", "path", "checkpoints", "rest_stops",
        ]

    def get_distance_mi(self, obj: RouteOption) -> float:
        return round(obj.distance_m / METERS_PER_MILE, 1)


class TripPlanSerializer(serializers.ModelSerializer):
    routes = RouteOptionSerializer(many=True, read_only=True)
    origin = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()
    recommendation = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            "id", "created_at", "origin", "destination", "departure_at", "load_lb",
            "interval_mi", "wind_mode", "hos_enabled", "recommendation", "notes",
            "weather_meta", "routes",
        ]

    def get_origin(self, obj: TripPlan) -> dict:
        return {"label": obj.origin_label, "lat": obj.origin_lat, "lon": obj.origin_lon,
                "tz": obj.origin_tz}

    def get_destination(self, obj: TripPlan) -> dict:
        return {"label": obj.dest_label, "lat": obj.dest_lat, "lon": obj.dest_lon,
                "tz": obj.dest_tz}

    def get_recommendation(self, obj: TripPlan) -> dict:
        return {"label": obj.recommended_label, "headline": obj.recommendation,
                "decided_by": obj.decided_by, "tradeoff": obj.tradeoff or None,
                "why_not": obj.why_not, "warnings": obj.warnings}
