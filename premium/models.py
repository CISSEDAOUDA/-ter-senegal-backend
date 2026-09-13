from django.db import models

from billetterie.models import Wagon
from comptes.models import Passager


class TypeServicePremium(models.TextChoices):
    WIFI = "WIFI", "Wi-Fi"
    PRISE_ELECTRIQUE = "PRISE_ELECTRIQUE", "Prise electrique"
    CLIMATISATION = "CLIMATISATION", "Climatisation"
    CONFORT_SIEGE = "CONFORT_SIEGE", "Confort du siege"


class ServicePremium(models.Model):
    """
    Suivi de disponibilite d'une prestation dans le wagon 1ere classe
    dedie. Rattache au Wagon (pas au Train) : c'est bien un wagon
    specifique du TER qui porte le service premium.
    """
    wagon = models.OneToOneField(Wagon, on_delete=models.CASCADE, related_name="service_premium")
    type = models.CharField(max_length=20, choices=TypeServicePremium.choices)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        etat = "disponible" if self.disponible else "indisponible"
        return f"{self.get_type_display()} ({etat}) - {self.wagon}"


class StatutReclamation(models.TextChoices):
    OUVERTE = "OUVERTE", "Ouverte"
    EN_COURS = "EN_COURS", "En cours"
    RESOLUE = "RESOLUE", "Resolue"


class Reclamation(models.Model):
    passager = models.ForeignKey(Passager, on_delete=models.CASCADE, related_name="reclamations")
    # Optionnel : reclamation generale (proprete, sur-occupation) si non renseigne.
    service_premium = models.ForeignKey(
        ServicePremium, on_delete=models.SET_NULL, null=True, blank=True, related_name="reclamations"
    )
    description = models.TextField(max_length=1000)
    statut = models.CharField(max_length=10, choices=StatutReclamation.choices, default=StatutReclamation.OUVERTE)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reclamation #{self.pk} - {self.passager} ({self.get_statut_display()})"
