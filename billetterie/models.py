from django.db import models

from comptes.models import AgentGare, Passager


class Gare(models.Model):
    """Arret de la ligne TER. `ordre` sert au calcul des troncons (3.5)."""
    nom = models.CharField(max_length=100, unique=True)
    ordre = models.PositiveSmallIntegerField(help_text="1 = Dakar, ... 11 = Diamniadio")

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.nom


class Train(models.Model):
    numero = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.numero


class ClasseWagon(models.TextChoices):
    PREMIERE = "PREMIERE", "1ere classe"
    DEUXIEME = "DEUXIEME", "2e classe"


class Wagon(models.Model):
    """
    Le TER a un wagon dedie au service premium : c'est CE wagon
    (classe=PREMIERE) qui porte la relation vers ServicePremium.
    """
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name="wagons")
    numero = models.CharField(max_length=10)
    classe = models.CharField(max_length=10, choices=ClasseWagon.choices)

    class Meta:
        unique_together = ("train", "numero")

    def __str__(self):
        return f"Wagon {self.numero} ({self.get_classe_display()}) - {self.train}"


class Siege(models.Model):
    wagon = models.ForeignKey(Wagon, on_delete=models.CASCADE, related_name="sieges")
    numero = models.CharField(max_length=10)

    class Meta:
        unique_together = ("wagon", "numero")

    def __str__(self):
        return f"Siege {self.numero} - {self.wagon}"


class Voyage(models.Model):
    """
    Depart precis d'un Train (train + horaire + gares). Le Billet
    reserve une place sur un Voyage, pas directement sur un Train -
    necessaire pour le reporting par troncon et heure de pointe (3.5).
    """
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name="voyages")
    gare_depart = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="voyages_au_depart")
    gare_arrivee = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="voyages_a_larrivee")
    date_heure_depart = models.DateTimeField()
    date_heure_arrivee = models.DateTimeField()

    class Meta:
        ordering = ["date_heure_depart"]

    def __str__(self):
        return f"{self.train} : {self.gare_depart} -> {self.gare_arrivee} ({self.date_heure_depart:%d/%m %H:%M})"


class Tarif(models.Model):
    """
    Prix 1ere classe parametrable et historise (section 3.6). Un Billet
    garde une reference vers le Tarif applique au moment de l'achat.
    """
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_effet = models.DateField()
    date_fin = models.DateField(null=True, blank=True, help_text="Vide si encore en vigueur.")

    class Meta:
        ordering = ["-date_effet"]

    def __str__(self):
        return f"{self.montant} FCFA a partir du {self.date_effet}"


class StatutBillet(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    CONFIRME = "CONFIRME", "Confirme"
    ANNULE = "ANNULE", "Annule"


class Billet(models.Model):
    """
    Fusionne volontairement reservation et billet (statut EN_ATTENTE
    tant que le paiement n'est pas confirme) : le paiement est immediat
    dans les 3 canaux prevus (mobile, guichet, borne).
    """
    qr_code = models.CharField(max_length=255, unique=True)
    statut = models.CharField(max_length=15, choices=StatutBillet.choices, default=StatutBillet.EN_ATTENTE)
    date_achat = models.DateTimeField(auto_now_add=True)

    passager = models.ForeignKey(Passager, on_delete=models.CASCADE, related_name="billets")
    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, related_name="billets")
    siege = models.ForeignKey(Siege, on_delete=models.PROTECT, related_name="billets")
    tarif = models.ForeignKey(Tarif, on_delete=models.PROTECT, related_name="billets")

    # Nul si achat via app mobile ou borne (pas d'agent implique).
    agent_gare = models.ForeignKey(
        AgentGare, on_delete=models.SET_NULL, null=True, blank=True, related_name="billets_vendus"
    )

    def __str__(self):
        return f"Billet {self.qr_code} - {self.passager}"


class MethodePaiement(models.TextChoices):
    ORANGE_MONEY = "ORANGE_MONEY", "Orange Money"
    WAVE = "WAVE", "Wave"
    GUICHET = "GUICHET", "Guichet"
    BORNE = "BORNE", "Borne automatique"


class Paiement(models.Model):
    billet = models.OneToOneField(Billet, on_delete=models.CASCADE, related_name="paiement")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    methode = models.CharField(max_length=15, choices=MethodePaiement.choices)
    date_paiement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paiement {self.montant} FCFA ({self.get_methode_display()}) - {self.billet}"
