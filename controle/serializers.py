from rest_framework import serializers

from billetterie.models import Billet, Gare, StatutBillet
from billetterie.serializers import BilletSerializer, GareSerializer
from comptes.serializers import ControleurSerializer

from .models import Controle, ResultatControle


class ControleSerializer(serializers.ModelSerializer):
    controleur = ControleurSerializer(read_only=True)
    billet = BilletSerializer(read_only=True)
    gare = GareSerializer(read_only=True)

    class Meta:
        model = Controle
        fields = ["id", "controleur", "billet", "gare", "resultat", "date_controle"]


class ScanBilletSerializer(serializers.Serializer):
    """
    Scan d'un billet a bord (cahier des charges, section 3.3). Le
    resultat est determine automatiquement : billet inconnu -> fraude,
    billet non confirme -> expire, mauvaise classe si le siege n'est
    pas dans le wagon premium.
    """
    qr_code = serializers.CharField()
    gare_id = serializers.PrimaryKeyRelatedField(source="gare", queryset=Gare.objects.all())

    def validate_qr_code(self, value):
        self._billet = Billet.objects.select_related("siege__wagon").filter(qr_code=value).first()
        return value

    def create(self, validated_data):
        from billetterie.models import ClasseWagon

        controleur = self.context["controleur"]
        gare = validated_data["gare"]
        billet = getattr(self, "_billet", None)

        if billet is None:
            raise serializers.ValidationError(
                {"qr_code": "Aucun billet ne correspond à ce QR code (fraude possible)."}
            )

        deja_valide = Controle.objects.filter(billet=billet, resultat=ResultatControle.VALIDE).exists()

        if deja_valide:
            # Le billet a deja ete scanne et valide une premiere fois -
            # le rescanner est un signal de reutilisation/fraude (billet
            # partage, capture d'ecran transmise a un tiers, etc.).
            resultat = ResultatControle.DEJA_VALIDE
        elif billet.statut != StatutBillet.CONFIRME:
            resultat = ResultatControle.BILLET_EXPIRE
        elif billet.siege.wagon.classe != ClasseWagon.PREMIERE:
            resultat = ResultatControle.MAUVAISE_CLASSE
        else:
            resultat = ResultatControle.VALIDE

        controle = Controle.objects.create(
            controleur=controleur, billet=billet, gare=gare, resultat=resultat
        )

        if resultat == ResultatControle.VALIDE:
            from notifications.models import Notification, TypeNotification
            Notification.objects.create(
                passager=billet.passager,
                type=TypeNotification.SMS,
                message=f"TER Senegal : votre billet a ete valide à la gare de {gare.nom}. Bon voyage !",
            )

        return controle