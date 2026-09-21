from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AchatBilletView, BilletViewSet, GareViewSet, PaiementViewSet,
    RechercherVoyageView, SiegeViewSet, StatistiquesView, TarifViewSet,
    TrainViewSet, VoyageViewSet, WagonViewSet,
)

router = DefaultRouter()
router.register("gares", GareViewSet, basename="gare")
router.register("trains", TrainViewSet, basename="train")
router.register("wagons", WagonViewSet, basename="wagon")
router.register("sieges", SiegeViewSet, basename="siege")
router.register("voyages", VoyageViewSet, basename="voyage")
router.register("tarifs", TarifViewSet, basename="tarif")
router.register("billets", BilletViewSet, basename="billet")
router.register("paiements", PaiementViewSet, basename="paiement")

urlpatterns = [
    path("achat/", AchatBilletView.as_view(), name="achat-billet"),
    path("voyages/rechercher/", RechercherVoyageView.as_view(), name="rechercher-voyage"),
    path("statistiques/", StatistiquesView.as_view(), name="statistiques"),
] + router.urls
