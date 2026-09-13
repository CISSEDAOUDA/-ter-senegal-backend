from django.db import IntegrityError
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Billet, ClasseWagon, Gare, Paiement, Siege, Tarif, Train, Voyage, Wagon
from .serializers import (
    AchatBilletSerializer,
    BilletSerializer,
    GareSerializer,
    PaiementSerializer,
    SiegeSerializer,
    TarifSerializer,
    TrainSerializer,
    VoyageSerializer,
    WagonSerializer,
)


class GareViewSet(viewsets.ModelViewSet):
    queryset = Gare.objects.all()
    serializer_class = GareSerializer


class TrainViewSet(viewsets.ModelViewSet):
    queryset = Train.objects.prefetch_related("wagons__sieges").all()
    serializer_class = TrainSerializer


class WagonViewSet(viewsets.ModelViewSet):
    queryset = Wagon.objects.select_related("train").prefetch_related("sieges").all()
    serializer_class = WagonSerializer


class SiegeViewSet(viewsets.ModelViewSet):
    queryset = Siege.objects.select_related("wagon").all()
    serializer_class = SiegeSerializer


class VoyageViewSet(viewsets.ModelViewSet):
    queryset = Voyage.objects.select_related("train", "gare_depart", "gare_arrivee").all()
    serializer_class = VoyageSerializer

    @action(detail=True, methods=["get"], url_path="sieges-disponibles")
    def sieges_disponibles(self, request, pk=None):
        voyage = self.get_object()
        sieges_du_train = Siege.objects.filter(
            wagon__train=voyage.train, wagon__classe=ClasseWagon.PREMIERE
        )
        sieges_pris = Billet.objects.filter(
            voyage=voyage, statut__in=["EN_ATTENTE", "CONFIRME"]
        ).values_list("siege_id", flat=True)
        disponibles = sieges_du_train.exclude(id__in=sieges_pris)
        return Response(SiegeSerializer(disponibles, many=True).data)


class TarifViewSet(viewsets.ModelViewSet):
    queryset = Tarif.objects.all()
    serializer_class = TarifSerializer

    @action(detail=False, methods=["get"], url_path="actuel")
    def actuel(self, request):
        from django.utils import timezone

        tarif = Tarif.objects.filter(
            date_effet__lte=timezone.now().date()
        ).order_by("-date_effet").first()
        if tarif is None:
            return Response({"detail": "Aucun tarif en vigueur."}, status=404)
        return Response(TarifSerializer(tarif).data)


class BilletViewSet(viewsets.ModelViewSet):
    queryset = Billet.objects.select_related(
        "passager__utilisateur", "voyage__gare_depart", "voyage__gare_arrivee",
        "siege__wagon", "tarif", "paiement",
    ).all()
    serializer_class = BilletSerializer
    http_method_names = ["get", "head", "options", "delete"]

    def get_queryset(self):
        base = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return base
        passager = getattr(user, "passager", None)
        if passager is None:
            return base.none()
        return base.filter(passager=passager)

    def destroy(self, request, *args, **kwargs):
        billet = self.get_object()
        deja_valide = billet.controles.filter(resultat="VALIDE").exists()
        if not deja_valide and not request.user.is_staff:
            raise serializers.ValidationError(
                "Ce billet n'a pas encore ete valide par un controleur - suppression impossible."
            )
        return super().destroy(request, *args, **kwargs)


class PaiementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Paiement.objects.select_related("billet").all()
    serializer_class = PaiementSerializer


class AchatBilletView(APIView):
    def post(self, request):
        serializer = AchatBilletSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            billet = serializer.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"siege_id": "Ce siege est deja reserve pour ce voyage - choisissez-en un autre."}
            )
        return Response(BilletSerializer(billet).data, status=201)


class StatistiquesView(APIView):
    def get(self, request):
        from django.db.models import Count, Sum
        from django.db.models.functions import ExtractHour, TruncDate

        if getattr(request.user, "administrateur", None) is None:
            return Response({"detail": "Reserve aux administrateurs."}, status=403)

        billets_confirmes = Billet.objects.filter(statut="CONFIRME")

        troncons = (
            billets_confirmes.values("voyage__gare_depart__nom", "voyage__gare_arrivee__nom")
            .annotate(nombre_billets=Count("id"))
            .order_by("-nombre_billets")
        )
        passagers_par_troncon = [
            {
                "troncon": f"{r['voyage__gare_depart__nom']} -> {r['voyage__gare_arrivee__nom']}",
                "nombre_billets": r["nombre_billets"],
            }
            for r in troncons
        ]

        jours = (
            Paiement.objects.annotate(jour=TruncDate("date_paiement"))
            .values("jour")
            .annotate(montant_total=Sum("montant"))
            .order_by("jour")
        )
        recettes_par_jour = [
            {"date": str(r["jour"]), "montant_total": float(r["montant_total"])}
            for r in jours
        ]

        heures_pointe = list(
            billets_confirmes.annotate(heure=ExtractHour("voyage__date_heure_depart"))
            .values("heure")
            .annotate(nombre_billets=Count("id"))
            .order_by("heure")
        )

        from controle.models import Controle

        total_controles = Controle.objects.count()
        fraudes = Controle.objects.exclude(resultat="VALIDE").count()
        taux_fraude = round((fraudes / total_controles) * 100, 1) if total_controles else 0

        return Response({
            "passagers_par_troncon": passagers_par_troncon,
            "recettes_par_jour": recettes_par_jour,
            "heures_pointe": heures_pointe,
            "taux_fraude": {
                "total_controles": total_controles,
                "fraudes": fraudes,
                "taux_pourcentage": taux_fraude,
            },
        })