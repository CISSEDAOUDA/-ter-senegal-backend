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
    RechercheVoyageSerializer,
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


class VoyageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Voyage.objects.select_related("train", "gare_depart", "gare_arrivee").all()
    serializer_class = VoyageSerializer

    @action(detail=True, methods=["get"], url_path="sieges-disponibles")
    def sieges_disponibles(self, request, pk=None):
        voyage = self.get_object()
        sieges_du_train = Siege.objects.filter(wagon__train=voyage.train, wagon__classe=ClasseWagon.PREMIERE)
        sieges_pris = Billet.objects.filter(
            voyage=voyage, statut__in=["EN_ATTENTE", "CONFIRME"]
        ).values_list("siege_id", flat=True)
        disponibles = sieges_du_train.exclude(id__in=sieges_pris)
        return Response(SiegeSerializer(disponibles, many=True).data)


class RechercherVoyageView(APIView):
    def post(self, request):
        serializer = RechercheVoyageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultat = serializer.creer_voyage()
        return Response({
            "voyage": VoyageSerializer(resultat["voyage"]).data,
            "gare_embarquement": GareSerializer(resultat["gare_embarquement"]).data,
            "gare_debarquement": GareSerializer(resultat["gare_debarquement"]).data,
            "heure_embarquement": resultat["heure_embarquement"],
            "heure_debarquement": resultat["heure_debarquement"],
        })


class TarifViewSet(viewsets.ModelViewSet):
    queryset = Tarif.objects.all()
    serializer_class = TarifSerializer

    @action(detail=False, methods=["get"], url_path="actuel")
    def actuel(self, request):
        from django.utils import timezone
        tarif = Tarif.objects.filter(date_effet__lte=timezone.now().date()).order_by("-date_effet").first()
        if tarif is None:
            return Response({"detail": "Aucun tarif en vigueur."}, status=404)
        return Response(TarifSerializer(tarif).data)


class BilletViewSet(viewsets.ModelViewSet):
    """
    La "suppression" d'un billet par un passager est une suppression
    DOUCE (champ Billet.supprime=True) : le billet disparait de sa
    liste, mais reste en base avec son Paiement intact, pour que les
    statistiques (recettes, taux de remplissage...) restent exactes -
    un achat deja effectue reste comptabilise meme si le billet est
    supprime ensuite.
    """
    queryset = Billet.objects.select_related(
        "passager__utilisateur", "voyage__gare_depart", "voyage__gare_arrivee",
        "siege__wagon", "tarif", "paiement", "gare_embarquement", "gare_debarquement",
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
        # Un passager ne voit jamais ses billets supprimes.
        return base.filter(passager=passager, supprime=False)

    def destroy(self, request, *args, **kwargs):
        billet = self.get_object()
        billet.supprime = True
        billet.save(update_fields=["supprime"])
        return Response(status=204)


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
    """
    GET /api/billetterie/statistiques/
    Reserve aux administrateurs.
    """

    def get(self, request):
        from django.db.models import Count, Sum, F, ExpressionWrapper, DurationField, Avg
        from django.db.models.functions import ExtractHour, TruncDate

        if getattr(request.user, "administrateur", None) is None:
            return Response({"detail": "Reserve aux administrateurs."}, status=403)

        billets_confirmes = Billet.objects.filter(statut="CONFIRME")

        # --- Trafic par troncon (deja existant) ---
        troncons = (
            billets_confirmes.values("gare_embarquement__nom", "gare_debarquement__nom")
            .annotate(nombre_billets=Count("id"))
            .order_by("-nombre_billets")
        )
        passagers_par_troncon = [
            {"troncon": f"{r['gare_embarquement__nom']} -> {r['gare_debarquement__nom']}", "nombre_billets": r["nombre_billets"]}
            for r in troncons
        ]

        # --- Recettes par jour (deja existant) ---
        jours = (
            Paiement.objects.annotate(jour=TruncDate("date_paiement")).values("jour")
            .annotate(montant_total=Sum("montant")).order_by("jour")
        )
        recettes_par_jour = [{"date": str(r["jour"]), "montant_total": float(r["montant_total"])} for r in jours]

        # --- NOUVEAU : recettes par gare (gare d'embarquement) ---
        # Repond a la demande : "les gares qui recoivent le plus de recettes".
        recettes_gares = (
            Paiement.objects.filter(billet__statut="CONFIRME")
            .values("billet__gare_embarquement__nom")
            .annotate(montant_total=Sum("montant"), nombre_billets=Count("id"))
            .order_by("-montant_total")
        )
        recettes_par_gare = [
            {
                "gare": r["billet__gare_embarquement__nom"],
                "montant_total": float(r["montant_total"]),
                "nombre_billets": r["nombre_billets"],
            }
            for r in recettes_gares
        ]

        # --- NOUVEAU : recettes par methode de paiement ---
        # Montre la repartition Orange Money / Wave / Guichet / Borne -
        # utile pour savoir quels canaux de vente sont les plus utilises.
        methodes = (
            Paiement.objects.filter(billet__statut="CONFIRME")
            .values("methode")
            .annotate(montant_total=Sum("montant"), nombre_billets=Count("id"))
            .order_by("-montant_total")
        )
        recettes_par_methode = [
            {"methode": r["methode"], "montant_total": float(r["montant_total"]), "nombre_billets": r["nombre_billets"]}
            for r in methodes
        ]

        # --- NOUVEAU : taux de remplissage moyen ---
        # Billets vendus / places du wagon premium, par voyage ayant
        # vendu au moins un billet - donne une idee du taux d'occupation
        # reel des trains en circulation.
        voyages_avec_ventes = (
            billets_confirmes.values("voyage_id", "voyage__train_id")
            .annotate(nb_billets=Count("id", distinct=True))
        )
        taux_remplissage = None
        if voyages_avec_ventes:
            capacites = {}
            for train_id in {v["voyage__train_id"] for v in voyages_avec_ventes}:
                capacites[train_id] = Siege.objects.filter(
                    wagon__train_id=train_id, wagon__classe=ClasseWagon.PREMIERE
                ).count()
            ratios = [
                v["nb_billets"] / capacites[v["voyage__train_id"]]
                for v in voyages_avec_ventes
                if capacites.get(v["voyage__train_id"])
            ]
            if ratios:
                taux_remplissage = round(sum(ratios) / len(ratios) * 100, 1)

        # --- heures de pointe (deja existant) ---
        heures_pointe = list(
            billets_confirmes.annotate(heure=ExtractHour("voyage__date_heure_depart"))
            .values("heure").annotate(nombre_billets=Count("id")).order_by("heure")
        )

        from controle.models import Controle
        total_controles = Controle.objects.count()
        fraudes = Controle.objects.exclude(resultat="VALIDE").count()
        taux_fraude = round((fraudes / total_controles) * 100, 1) if total_controles else 0

        return Response({
            "passagers_par_troncon": passagers_par_troncon,
            "recettes_par_jour": recettes_par_jour,
            "recettes_par_gare": recettes_par_gare,
            "recettes_par_methode": recettes_par_methode,
            "taux_remplissage_moyen_pourcentage": taux_remplissage,
            "heures_pointe": heures_pointe,
            "taux_fraude": {"total_controles": total_controles, "fraudes": fraudes, "taux_pourcentage": taux_fraude},
        })