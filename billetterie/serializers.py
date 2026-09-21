from rest_framework import serializers

from comptes.models import Passager

from .models import (
    Billet, ClasseWagon, Gare, MethodePaiement, Paiement, Siege, StatutBillet, Tarif,
    Train, Voyage, Wagon, calculer_heure_passage, nettoyer_voyages_passes_non_vendus,
    obtenir_ou_creer_voyage,
)


class GareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gare
        fields = ["id", "nom", "ordre"]


class SiegeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Siege
        fields = ["id", "numero", "wagon"]


class WagonSerializer(serializers.ModelSerializer):
    sieges = SiegeSerializer(many=True, read_only=True)

    class Meta:
        model = Wagon
        fields = ["id", "numero", "classe", "train", "sieges"]


class TrainSerializer(serializers.ModelSerializer):
    wagons = WagonSerializer(many=True, read_only=True)

    class Meta:
        model = Train
        fields = ["id", "numero", "wagons"]


class VoyageSerializer(serializers.ModelSerializer):
    gare_depart = GareSerializer(read_only=True)
    gare_arrivee = GareSerializer(read_only=True)
    nombre_billets_vendus = serializers.SerializerMethodField()
    capacite = serializers.SerializerMethodField()
    statut_temporel = serializers.SerializerMethodField()

    class Meta:
        model = Voyage
        fields = [
            "id", "train", "gare_depart", "gare_arrivee", "date_heure_depart", "date_heure_arrivee",
            "nombre_billets_vendus", "capacite", "statut_temporel",
        ]

    def get_nombre_billets_vendus(self, obj):
        return obj.billets.filter(statut="CONFIRME").count()

    def get_capacite(self, obj):
        return Siege.objects.filter(wagon__train_id=obj.train_id, wagon__classe=ClasseWagon.PREMIERE).count()

    def get_statut_temporel(self, obj):
        from django.utils import timezone
        return "A_VENIR" if obj.date_heure_depart >= timezone.now() else "TERMINE"


class TarifSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarif
        fields = ["id", "montant", "date_effet", "date_fin"]


class PaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ["id", "billet", "montant", "methode", "date_paiement"]
        read_only_fields = ["date_paiement"]


class RechercheVoyageSerializer(serializers.Serializer):
    """
    POST /api/billetterie/voyages/rechercher/
    Body: {gare_embarquement_id, gare_debarquement_id, date_heure_souhaitee}

    Trouve (ou cree) le voyage le plus proche de la date/heure demandee,
    pour le trajet gare_embarquement -> gare_debarquement choisi par le
    passager - qui peuvent etre deux gares intermediaires quelconques de
    la ligne, pas necessairement les terminus (cf. billetterie/models.py
    pour le detail de l'algorithme).
    """
    gare_embarquement_id = serializers.PrimaryKeyRelatedField(source="gare_embarquement", queryset=Gare.objects.all())
    gare_debarquement_id = serializers.PrimaryKeyRelatedField(source="gare_debarquement", queryset=Gare.objects.all())
    date_heure_souhaitee = serializers.DateTimeField()

    def validate(self, data):
        if data["gare_embarquement"].id == data["gare_debarquement"].id:
            raise serializers.ValidationError("La gare de depart et d'arrivee doivent etre differentes.")
        return data

    def creer_voyage(self):
        nettoyer_voyages_passes_non_vendus()
        try:
            voyage, heure_embarquement, heure_debarquement = obtenir_ou_creer_voyage(
                self.validated_data["gare_embarquement"],
                self.validated_data["gare_debarquement"],
                self.validated_data["date_heure_souhaitee"],
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return {
            "voyage": voyage,
            "gare_embarquement": self.validated_data["gare_embarquement"],
            "gare_debarquement": self.validated_data["gare_debarquement"],
            "heure_embarquement": heure_embarquement,
            "heure_debarquement": heure_debarquement,
        }


class BilletSerializer(serializers.ModelSerializer):
    voyage = VoyageSerializer(read_only=True)
    tarif = TarifSerializer(read_only=True)
    siege = SiegeSerializer(read_only=True)
    paiement = PaiementSerializer(read_only=True)
    gare_embarquement = GareSerializer(read_only=True)
    gare_debarquement = GareSerializer(read_only=True)
    deja_utilise = serializers.SerializerMethodField()
    heure_embarquement = serializers.SerializerMethodField()
    heure_debarquement = serializers.SerializerMethodField()

    class Meta:
        model = Billet
        fields = [
            "id", "qr_code", "statut", "date_achat",
            "passager", "voyage", "siege", "tarif", "agent_gare", "paiement",
            "gare_embarquement", "gare_debarquement", "deja_utilise",
            "heure_embarquement", "heure_debarquement",
        ]
        read_only_fields = ["qr_code", "statut", "date_achat"]

    def get_deja_utilise(self, obj):
        return obj.controles.filter(resultat="VALIDE").exists()

    def get_heure_embarquement(self, obj):
        return calculer_heure_passage(obj.voyage, obj.gare_embarquement)

    def get_heure_debarquement(self, obj):
        return calculer_heure_passage(obj.voyage, obj.gare_debarquement)


class AchatBilletSerializer(serializers.Serializer):
    """
    Achat d'un billet. Le passager (ou l'agent de gare pour son compte)
    fournit desormais sa gare d'embarquement et de debarquement plutot
    qu'un voyage_id direct - le voyage correspondant est resolu (ou
    cree) automatiquement via obtenir_ou_creer_voyage().
    """
    passager_id = serializers.PrimaryKeyRelatedField(source="passager", queryset=Passager.objects.all())
    gare_embarquement_id = serializers.PrimaryKeyRelatedField(source="gare_embarquement", queryset=Gare.objects.all())
    gare_debarquement_id = serializers.PrimaryKeyRelatedField(source="gare_debarquement", queryset=Gare.objects.all())
    date_heure_souhaitee = serializers.DateTimeField()
    siege_id = serializers.PrimaryKeyRelatedField(source="siege", queryset=Siege.objects.all())
    methode_paiement = serializers.CharField()

    def validate(self, data):
        if data["gare_embarquement"].id == data["gare_debarquement"].id:
            raise serializers.ValidationError("La gare de depart et d'arrivee doivent etre differentes.")
        return data

    def create(self, validated_data):
        from django.db import transaction
        from django.utils import timezone
        import uuid

        passager = validated_data["passager"]
        siege = validated_data["siege"]
        methode = validated_data["methode_paiement"]

        tarif = Tarif.objects.filter(date_effet__lte=timezone.now().date()).order_by("-date_effet").first()
        if tarif is None:
            raise serializers.ValidationError("Aucun tarif en vigueur - contactez l'administration.")

        nettoyer_voyages_passes_non_vendus()
        try:
            voyage, _, _ = obtenir_ou_creer_voyage(
                validated_data["gare_embarquement"],
                validated_data["gare_debarquement"],
                validated_data["date_heure_souhaitee"],
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        request = self.context.get("request")
        agent_gare = None
        if request is not None:
            agent_gare = getattr(request.user, "agentgare", None)

        champ_solde = {
            MethodePaiement.ORANGE_MONEY: "solde_orange_money",
            MethodePaiement.WAVE: "solde_wave",
        }.get(methode)

        with transaction.atomic():
            if champ_solde:
                passager_verrouille = Passager.objects.select_for_update().get(pk=passager.pk)
                solde_actuel = getattr(passager_verrouille, champ_solde)
                if solde_actuel < tarif.montant:
                    raise serializers.ValidationError(
                        {"methode_paiement": f"Solde insuffisant ({solde_actuel} FCFA disponibles, {tarif.montant} FCFA requis)."}
                    )
                setattr(passager_verrouille, champ_solde, solde_actuel - tarif.montant)
                passager_verrouille.save(update_fields=[champ_solde])

            billet = Billet.objects.create(
                qr_code=str(uuid.uuid4()),
                statut=StatutBillet.EN_ATTENTE,
                passager=passager,
                voyage=voyage,
                siege=siege,
                tarif=tarif,
                gare_embarquement=validated_data["gare_embarquement"],
                gare_debarquement=validated_data["gare_debarquement"],
                agent_gare=agent_gare,
            )
            Paiement.objects.create(billet=billet, montant=tarif.montant, methode=methode)
            billet.statut = StatutBillet.CONFIRME
            billet.save(update_fields=["statut"])

            from notifications.models import Notification, TypeNotification
            heure_embarquement = calculer_heure_passage(voyage, validated_data["gare_embarquement"])
            Notification.objects.create(
                passager=passager,
                type=TypeNotification.SMS,
                message=(
                    f"TER Senegal : votre billet de {validated_data['gare_embarquement'].nom} a "
                    f"{validated_data['gare_debarquement'].nom}, embarquement prevu a "
                    f"{heure_embarquement.strftime('%d/%m/%Y a %H:%M')}, est confirme. "
                    f"Montant : {tarif.montant} FCFA."
                ),
            )
        return billet