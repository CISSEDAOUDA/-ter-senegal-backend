from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import Reclamation, ServicePremium
from .serializers import ReclamationSerializer, ServicePremiumSerializer


class ServicePremiumViewSet(viewsets.ModelViewSet):
    """
    Suivi de disponibilite Wi-Fi/prises/climatisation dans le wagon
    premium (cahier des charges, section 3.4).
    """
    queryset = ServicePremium.objects.select_related("wagon").all()
    serializer_class = ServicePremiumSerializer


class ReclamationViewSet(viewsets.ModelViewSet):
    """
    Un passager ne voit et ne cree que ses propres reclamations. Le
    ChefTrain (supervision des incidents a bord, cf. tableau des
    acteurs du rapport d'architecture) et l'Administrateur voient
    tout, pour pouvoir les traiter.
    """
    serializer_class = ReclamationSerializer

    def get_queryset(self):
        user = self.request.user
        base = Reclamation.objects.select_related(
            "passager__utilisateur", "service_premium__wagon"
        )
        peut_tout_voir = (
            user.is_staff
            or getattr(user, "cheftrain", None) is not None
            or getattr(user, "administrateur", None) is not None
        )
        if peut_tout_voir:
            return base.all()
        return base.filter(passager__utilisateur=user)

    def perform_create(self, serializer):
        passager = getattr(self.request.user, "passager", None)
        if passager is None:
            raise PermissionDenied("Seul un passager peut soumettre une reclamation.")
        serializer.save(passager=passager)

    @action(detail=True, methods=["patch"], url_path="changer-statut")
    def changer_statut(self, request, pk=None):
        """
        PATCH /api/premium/reclamations/{id}/changer-statut/
        Body: {statut: "EN_COURS" | "RESOLUE" | "OUVERTE"}
        Reserve au ChefTrain/Administrateur/staff (le champ statut est
        en lecture seule dans le serializer principal, volontairement,
        pour qu'un passager ne puisse pas cloturer sa propre reclamation).
        """
        user = request.user
        autorise = (
            user.is_staff
            or getattr(user, "cheftrain", None) is not None
            or getattr(user, "administrateur", None) is not None
        )
        if not autorise:
            raise PermissionDenied("Seul un chef de train ou un administrateur peut changer ce statut.")

        reclamation = self.get_object()
        nouveau_statut = request.data.get("statut")
        if nouveau_statut not in ["OUVERTE", "EN_COURS", "RESOLUE"]:
            raise serializers.ValidationError({"statut": "Valeur invalide."})
        reclamation.statut = nouveau_statut
        reclamation.save(update_fields=["statut"])
        return Response(ReclamationSerializer(reclamation).data)