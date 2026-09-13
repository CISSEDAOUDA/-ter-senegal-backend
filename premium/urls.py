from rest_framework.routers import DefaultRouter

from .views import ReclamationViewSet, ServicePremiumViewSet

router = DefaultRouter()
router.register("services", ServicePremiumViewSet, basename="service-premium")
router.register("reclamations", ReclamationViewSet, basename="reclamation")

urlpatterns = router.urls
