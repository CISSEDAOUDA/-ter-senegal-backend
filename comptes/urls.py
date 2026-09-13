from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdministrateurViewSet,
    AgentGareViewSet,
    ChefTrainViewSet,
    ControleurViewSet,
    InscriptionPassagerView,
    MoiView,
    PassagerViewSet,
)

router = DefaultRouter()
router.register("passagers", PassagerViewSet, basename="passager")
router.register("administrateurs", AdministrateurViewSet, basename="administrateur")
router.register("controleurs", ControleurViewSet, basename="controleur")
router.register("agents-gare", AgentGareViewSet, basename="agent-gare")
router.register("chefs-train", ChefTrainViewSet, basename="chef-train")

urlpatterns = [
    path("inscription/", InscriptionPassagerView.as_view(), name="inscription-passager"),
    path("moi/", MoiView.as_view(), name="moi"),
] + router.urls
