from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Administrateur, AgentGare, ChefTrain, Controleur, Passager, Utilisateur


class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ["id", "username", "first_name", "last_name", "email", "telephone"]


class PassagerSerializer(serializers.ModelSerializer):
    utilisateur = UtilisateurSerializer(read_only=True)

    class Meta:
        model = Passager
        fields = ["id", "utilisateur", "numero_piece_identite", "numero_ter_card"]


class PassagerInscriptionSerializer(serializers.ModelSerializer):
    """
    Inscription d'un nouveau passager : cree Utilisateur + Passager en
    une seule requete (cahier des charges, section 3.1).
    """
    username = serializers.CharField(
        write_only=True,
        validators=[UniqueValidator(queryset=Utilisateur.objects.all(), message="Ce nom d'utilisateur est deja pris.")],
    )
    email = serializers.EmailField(
        write_only=True,
        validators=[UniqueValidator(queryset=Utilisateur.objects.all(), message="Cet email est deja utilise.")],
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    telephone = serializers.CharField(write_only=True)

    class Meta:
        model = Passager
        fields = [
            "id", "username", "email", "password", "first_name", "last_name",
            "telephone", "numero_piece_identite", "numero_ter_card",
        ]

    def create(self, validated_data):
        utilisateur = Utilisateur.objects.create_user(
            username=validated_data.pop("username"),
            email=validated_data.pop("email"),
            password=validated_data.pop("password"),
            first_name=validated_data.pop("first_name"),
            last_name=validated_data.pop("last_name"),
            telephone=validated_data.pop("telephone"),
        )
        return Passager.objects.create(utilisateur=utilisateur, **validated_data)


class _PersonnelSerializerBase(serializers.ModelSerializer):
    utilisateur = UtilisateurSerializer(read_only=True)


class AdministrateurSerializer(_PersonnelSerializerBase):
    class Meta:
        model = Administrateur
        fields = ["id", "utilisateur", "matricule"]


class ControleurSerializer(_PersonnelSerializerBase):
    class Meta:
        model = Controleur
        fields = ["id", "utilisateur", "matricule"]


class AgentGareSerializer(_PersonnelSerializerBase):
    class Meta:
        model = AgentGare
        fields = ["id", "utilisateur", "matricule"]


class ChefTrainSerializer(_PersonnelSerializerBase):
    class Meta:
        model = ChefTrain
        fields = ["id", "utilisateur", "matricule"]
