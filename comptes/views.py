from rest_framework import permissions, viewsets
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Administrateur, AgentGare, ChefTrain, Controleur, Passager
from .serializers import (
    AdministrateurSerializer,
    AgentGareSerializer,
    ChefTrainSerializer,
    ControleurSerializer,
    PassagerInscriptionSerializer,
    PassagerSerializer,
    UtilisateurSerializer,
)


class MoiView(APIView):
    def get(self, request):
        user = request.user
        for role, attr in [
            ("PASSAGER", "passager"),
            ("CONTROLEUR", "controleur"),
            ("AGENT_GARE", "agentgare"),
            ("CHEF_TRAIN", "cheftrain"),
            ("ADMIN", "administrateur"),
        ]:
            profil = getattr(user, attr, None)
            if profil is not None:
                reponse = {
                    "utilisateur": UtilisateurSerializer(user).data,
                    "role": role,
                    "profil_id": profil.id,
                }
                if role == "PASSAGER":
                    reponse["soldes"] = {
                        "ORANGE_MONEY": profil.solde_orange_money,
                        "WAVE": profil.solde_wave,
                    }
                return Response(reponse)
        return Response({"utilisateur": UtilisateurSerializer(user).data, "role": None, "profil_id": None})


class InscriptionPassagerView(CreateAPIView):
    queryset = Passager.objects.all()
    serializer_class = PassagerInscriptionSerializer
    permission_classes = [permissions.AllowAny]


class PassagerViewSet(viewsets.ModelViewSet):
    queryset = Passager.objects.select_related("utilisateur").all()
    serializer_class = PassagerSerializer

    def get_queryset(self):
        base = super().get_queryset()
        recherche = self.request.query_params.get("recherche")
        if recherche:
            from django.db.models import Q
            base = base.filter(
                Q(numero_piece_identite__icontains=recherche)
                | Q(utilisateur__username__icontains=recherche)
                | Q(utilisateur__first_name__icontains=recherche)
                | Q(utilisateur__last_name__icontains=recherche)
            )
        return base


class AdministrateurViewSet(viewsets.ModelViewSet):
    queryset = Administrateur.objects.select_related("utilisateur").all()
    serializer_class = AdministrateurSerializer


class ControleurViewSet(viewsets.ModelViewSet):
    queryset = Controleur.objects.select_related("utilisateur").all()
    serializer_class = ControleurSerializer


class AgentGareViewSet(viewsets.ModelViewSet):
    queryset = AgentGare.objects.select_related("utilisateur").all()
    serializer_class = AgentGareSerializer


class ChefTrainViewSet(viewsets.ModelViewSet):
    queryset = ChefTrain.objects.select_related("utilisateur").all()
    serializer_class = ChefTrainSerializer