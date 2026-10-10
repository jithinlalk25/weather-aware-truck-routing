from django.contrib import admin

from .models import RouteOption, TripPlan


class RouteOptionInline(admin.TabularInline):
    model = RouteOption
    fields = ("label", "rank", "source", "distance_m", "total_s", "miles_by_level", "avg_risk")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(TripPlan)
class TripPlanAdmin(admin.ModelAdmin):
    list_display = ("created_at", "origin_label", "dest_label", "departure_at", "load_lb",
                    "interval_mi", "wind_mode", "hos_enabled", "recommended_label")
    list_filter = ("wind_mode", "hos_enabled", "interval_mi")
    search_fields = ("origin_label", "dest_label")
    exclude = ("heatmap",)
    inlines = [RouteOptionInline]
