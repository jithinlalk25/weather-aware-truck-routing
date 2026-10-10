from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view()),
    path("geocode", views.GeocodeView.as_view()),
    path("plans", views.PlanListCreateView.as_view()),
    path("plans/<uuid:plan_id>", views.PlanDetailView.as_view()),
    path("plans/<uuid:plan_id>/heatmap", views.PlanHeatmapView.as_view()),
]
