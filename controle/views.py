from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Controle
from .serializers import ControleSerializer, ScanBilletSerializer


class ControleViewSet(viewsets.ReadOnlyModelViewSet):
    """Historique des controles - consultation seule (creation via ScanBilletView)."""
    queryset = Controle.objects.select_related(
        "controleur__utilisateur", "billet__passager__utilisateur", "gare"
    ).all()
    serializer_class = ControleSerializer


class ScanBilletView(APIView):
    """
    POST /api/controle/scan/
    Body: {qr_code, gare_id}
    Reserve aux utilisateurs ayant un profil Controleur.
    """

    def post(self, request):
        controleur = getattr(request.user, "controleur", None)
        if controleur is None:
            raise PermissionDenied("Seul un controleur peut scanner un billet.")

        serializer = ScanBilletSerializer(data=request.data, context={"controleur": controleur})
        serializer.is_valid(raise_exception=True)
        controle = serializer.save()
        return Response(ControleSerializer(controle).data, status=201)
