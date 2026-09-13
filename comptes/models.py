from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """
    Utilisateur custom Django, base de tous les acteurs du systeme
    (cf. section 1.2 du rapport d'architecture). Reprend email/mot de
    passe/permissions d'AbstractUser et ajoute le telephone.

    Le role reel (Passager, Administrateur, Controleur, AgentGare,
    ChefTrain) est porte par le profil OneToOne associe - equivalent
    Django idiomatique de l'heritage JOINED du diagramme de classes.
    """
    telephone = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class Personnel(models.Model):
    """
    Classe abstraite (pas de table propre) factorisant le matricule
    commun aux profils internes SENTER.
    """
    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="%(class)s"
    )
    matricule = models.CharField(max_length=30, unique=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.matricule} - {self.utilisateur}"


class Administrateur(Personnel):
    """Gestionnaire systeme : tarifs, trains/wagons/horaires, utilisateurs."""


class Controleur(Personnel):
    """Agent SENTER : scan des billets a bord, signalement des fraudes."""


class AgentGare(Personnel):
    """Guichetier : vente de billets, gestion des abonnements."""


class ChefTrain(Personnel):
    """Superviseur a bord : wagons, incidents."""


class Passager(models.Model):
    """
    Voyageur 1ere classe. Porte la piece d'identite et, le cas echeant,
    le numero de TER Card (abonnement mensuel) - cahier des charges
    section 3.1. L'historique des voyages se deduit des billets lies.

    solde_orange_money / solde_wave : soldes simules pour la demo du
    paiement mobile (pas d'integration reelle possible sans compte
    marchand - cf. memoire, chapitre "difficultes rencontrees"). Debites
    a chaque achat pour rendre la simulation dynamique et realiste.
    """
    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="passager"
    )
    numero_piece_identite = models.CharField(max_length=30, unique=True)
    numero_ter_card = models.CharField(
        max_length=30, unique=True, null=True, blank=True,
        help_text="Vide si le passager n'a pas d'abonnement mensuel.",
    )
    solde_orange_money = models.DecimalField(max_digits=10, decimal_places=2, default=5000)
    solde_wave = models.DecimalField(max_digits=10, decimal_places=2, default=5000)

    def __str__(self):
        return f"{self.utilisateur} - CNI {self.numero_piece_identite}"