from rest_framework import serializers

from comptes.models import Passager

from .models import Billet, Gare, Paiement, Siege, Tarif, Train, Voyage, Wagon


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
    gare_depart_id = serializers.PrimaryKeyRelatedField(
        source="gare_depart", queryset=Gare.objects.all(), write_only=True
    )
    gare_arrivee_id = serializers.PrimaryKeyRelatedField(
        source="gare_arrivee", queryset=Gare.objects.all(), write_only=True
    )

    class Meta:
        model = Voyage
        fields = [
            "id", "train", "gare_depart", "gare_arrivee",
            "gare_depart_id", "gare_arrivee_id",
            "date_heure_depart", "date_heure_arrivee",
        ]


class TarifSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarif
        fields = ["id", "montant", "date_effet", "date_fin"]


class PaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ["id", "billet", "montant", "methode", "date_paiement"]
        read_only_fields = ["date_paiement"]


class BilletSerializer(serializers.ModelSerializer):
    voyage = VoyageSerializer(read_only=True)
    tarif = TarifSerializer(read_only=True)
    siege = SiegeSerializer(read_only=True)
    paiement = PaiementSerializer(read_only=True)
    deja_utilise = serializers.SerializerMethodField()

    class Meta:
        model = Billet
        fields = [
            "id", "qr_code", "statut", "date_achat",
            "passager", "voyage", "siege", "tarif", "agent_gare", "paiement",
            "deja_utilise",
        ]
        read_only_fields = ["qr_code", "statut", "date_achat"]

    def get_deja_utilise(self, obj):
        """
        Vrai si un controleur a deja scanne ce billet avec succes
        (resultat VALIDE) - condition necessaire pour pouvoir le
        supprimer (cf. BilletViewSet.destroy).
        """
        return obj.controles.filter(resultat="VALIDE").exists()


class AchatBilletSerializer(serializers.Serializer):
    """
    Achat d'un billet en une requete : cree le Billet (statut EN_ATTENTE
    puis CONFIRME) et le Paiement associe (cahier des charges, section
    3.2 : mobile, guichet ou borne + confirmation QR).

    Pour Orange Money/Wave, debite un solde simule sur le Passager (pas
    d'integration reelle possible sans compte marchand) - rend la
    simulation dynamique : solde insuffisant = achat refuse.
    """
    passager_id = serializers.PrimaryKeyRelatedField(source="passager", queryset=Passager.objects.all())
    voyage_id = serializers.PrimaryKeyRelatedField(source="voyage", queryset=Voyage.objects.all())
    siege_id = serializers.PrimaryKeyRelatedField(source="siege", queryset=Siege.objects.all())
    methode_paiement = serializers.CharField()

    def create(self, validated_data):
        from django.db import transaction
        from django.utils import timezone
        import uuid

        from .models import MethodePaiement, StatutBillet

        passager = validated_data["passager"]
        voyage = validated_data["voyage"]
        siege = validated_data["siege"]
        methode = validated_data["methode_paiement"]

        tarif = Tarif.objects.filter(date_effet__lte=timezone.now().date()).order_by("-date_effet").first()
        if tarif is None:
            raise serializers.ValidationError("Aucun tarif en vigueur - contactez l'administration.")

        # Si la vente est effectuee par un agent de gare (guichet), on
        # trace qui a vendu le billet (cahier des charges, section 3.2).
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
                # Verrouille la ligne passager le temps de la transaction
                # pour eviter un double-debit en cas de requetes simultanees.
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
                agent_gare=agent_gare,
            )
            Paiement.objects.create(
                billet=billet,
                montant=tarif.montant,
                methode=methode,
            )
            billet.statut = StatutBillet.CONFIRME
            billet.save(update_fields=["statut"])

            from notifications.models import Notification, TypeNotification
            Notification.objects.create(
                passager=passager,
                type=TypeNotification.SMS,
                message=(
                    f"TER Senegal : votre billet 1ere classe pour le "
                    f"{voyage.date_heure_depart.strftime('%d/%m/%Y a %H:%M')} "
                    f"est confirme. Montant : {tarif.montant} FCFA."
                ),
            )
        return billet