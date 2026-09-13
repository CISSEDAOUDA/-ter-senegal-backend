from django.db import models

from billetterie.models import Billet, Gare
from comptes.models import Controleur


class ResultatControle(models.TextChoices):
    VALIDE = "VALIDE", "Valide"
    BILLET_EXPIRE = "BILLET_EXPIRE", "Billet expire"
    MAUVAISE_CLASSE = "MAUVAISE_CLASSE", "Mauvaise classe"
    FRAUDE_QR = "FRAUDE_QR", "Fraude QR"
    DEJA_VALIDE = "DEJA_VALIDE", "Deja valide (reutilisation)"

class Controle(models.Model):
    """
    Scan d'un billet a bord par un Controleur (cahier des charges,
    section 3.3 : billet expire / mauvaise classe / QR falsifie).
    """
    controleur = models.ForeignKey(Controleur, on_delete=models.CASCADE, related_name="controles")
    billet = models.ForeignKey(Billet, on_delete=models.CASCADE, related_name="controles")
    # Gare d'embarquement effective au moment du scan (correspondance
    # avec la gare de depart declaree sur le billet).
    gare = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="controles")
    resultat = models.CharField(max_length=20, choices=ResultatControle.choices)
    date_controle = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Controle {self.billet} - {self.get_resultat_display()}"
