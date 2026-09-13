from rest_framework import serializers

from billetterie.serializers import WagonSerializer
from comptes.serializers import PassagerSerializer

from .models import Reclamation, ServicePremium


class ServicePremiumSerializer(serializers.ModelSerializer):
    wagon = WagonSerializer(read_only=True)

    class Meta:
        model = ServicePremium
        fields = ["id", "wagon", "type", "disponible"]


class ReclamationSerializer(serializers.ModelSerializer):
    passager = PassagerSerializer(read_only=True)
    service_premium = ServicePremiumSerializer(read_only=True)
    service_premium_id = serializers.PrimaryKeyRelatedField(
        source="service_premium", queryset=ServicePremium.objects.all(),
        write_only=True, required=False, allow_null=True,
    )

    class Meta:
        model = Reclamation
        fields = [
            "id", "passager", "service_premium", "service_premium_id",
            "description", "statut", "date_creation",
        ]
        read_only_fields = ["statut", "date_creation"]

    def create(self, validated_data):
        return Reclamation.objects.create(**validated_data)
