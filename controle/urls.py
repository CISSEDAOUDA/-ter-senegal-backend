from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ControleViewSet, ScanBilletView

router = DefaultRouter()
router.register("historique", ControleViewSet, basename="controle")

urlpatterns = [
    path("scan/", ScanBilletView.as_view(), name="scan-billet"),
] + router.urls
