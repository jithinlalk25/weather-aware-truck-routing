from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import TripPlan
from .serializers import PlanRequestSerializer, TripPlanSerializer
from .services.geocode import search_places
from .services.heatmap import build_heatmap
from .services.planner import Place, PlanRequest, build_plan


class HealthView(APIView):
    def get(self, request):
        return Response({"ok": True})


class GeocodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            return Response({"results": []})
        return Response({"results": search_places(q)})


class PlanCreateView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "plans"

    def post(self, request):
        s = PlanRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        plan = build_plan(PlanRequest(
            origin=Place(**d["origin"]),
            destination=Place(**d["destination"]),
            departure_local=d["departure_local"].replace(tzinfo=None),
            load_lb=d["load_lb"],
            interval_mi=int(d["interval_mi"]),
            wind_mode=d["wind_mode"],
            hos=d["hos"],
        ))
        plan = TripPlan.objects.prefetch_related("routes").get(pk=plan.pk)
        return Response(TripPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    def get(self, request, plan_id):
        plan = get_object_or_404(TripPlan.objects.prefetch_related("routes"), pk=plan_id)
        return Response(TripPlanSerializer(plan).data)


class PlanHeatmapView(APIView):
    def get(self, request, plan_id):
        plan = get_object_or_404(TripPlan, pk=plan_id)
        if plan.heatmap is not None:
            return Response(plan.heatmap)
        heatmap = build_heatmap(plan)
        if heatmap["complete"]:  # don't freeze gaps from a transient weather outage
            plan.heatmap = heatmap
            plan.heatmap_computed_at = timezone.now()
            plan.save(update_fields=["heatmap", "heatmap_computed_at"])
        return Response(heatmap)
