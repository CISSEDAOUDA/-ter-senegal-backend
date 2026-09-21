from django.db import models
from comptes.models import AgentGare, Passager


# ============================================================
# GARE
# ============================================================

class Gare(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    ordre = models.PositiveSmallIntegerField(
        help_text="1 = Dakar, ... 11 = Diamniadio"
    )

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.nom


# ============================================================
# TRAIN
# ============================================================

class Train(models.Model):
    numero = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.numero


# ============================================================
# CLASSE WAGON
# ============================================================

class ClasseWagon(models.TextChoices):
    PREMIERE = "PREMIERE", "1ere classe"
    DEUXIEME = "DEUXIEME", "2e classe"


# ============================================================
# WAGON
# ============================================================

class Wagon(models.Model):
    train = models.ForeignKey(
        Train,
        on_delete=models.CASCADE,
        related_name="wagons"
    )

    numero = models.CharField(max_length=10)

    classe = models.CharField(
        max_length=10,
        choices=ClasseWagon.choices
    )

    class Meta:
        unique_together = ("train", "numero")

    def __str__(self):
        return (
            f"Wagon {self.numero} "
            f"({self.get_classe_display()}) - {self.train}"
        )


# ============================================================
# SIEGE
# ============================================================

class Siege(models.Model):
    wagon = models.ForeignKey(
        Wagon,
        on_delete=models.CASCADE,
        related_name="sieges"
    )

    numero = models.CharField(max_length=10)

    class Meta:
        unique_together = ("wagon", "numero")

    def __str__(self):
        return f"Siege {self.numero} - {self.wagon}"


# ============================================================
# PARAMETRES DE CIRCULATION
# ============================================================

INTERVALLE_DEPART_MINUTES = 10
DUREE_TRAJET_PAR_SEGMENT_MINUTES = 5
TEMPS_ARRET_GARE_MINUTES = 2

# Avec 11 gares : 10 segments x 5 minutes = 50 minutes de trajet pur
# (hors arrets intermediaires - la duree totale REELLE, arrets inclus,
# est calculee dynamiquement dans obtenir_ou_creer_voyage : 68 minutes
# avec 9 arrets de 2 min sur le trajet complet. Cette constante ne sert
# qu'a documenter le temps de trajet "pur", elle n'est pas utilisee
# directement dans les calculs).
DUREE_TOTALE_TRAJET_MINUTES = 50


# ============================================================
# VOYAGE
# ============================================================

class Voyage(models.Model):
    """
    Represente le trajet COMPLET d'un train, d'un terminus
    a l'autre.

    Le voyage est toujours defini entre les deux terminus.
    Le passager peut cependant choisir n'importe quelle gare
    comme gare d'embarquement et n'importe quelle gare suivante
    comme gare de debarquement.
    """

    train = models.ForeignKey(
        Train,
        on_delete=models.CASCADE,
        related_name="voyages"
    )

    gare_depart = models.ForeignKey(
        Gare,
        on_delete=models.PROTECT,
        related_name="voyages_au_depart"
    )

    gare_arrivee = models.ForeignKey(
        Gare,
        on_delete=models.PROTECT,
        related_name="voyages_a_larrivee"
    )

    date_heure_depart = models.DateTimeField()

    date_heure_arrivee = models.DateTimeField()

    class Meta:
        ordering = ["date_heure_depart"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "gare_depart",
                    "gare_arrivee",
                    "date_heure_depart"
                ],
                name="unique_voyage_par_creneau",
            )
        ]

    def __str__(self):
        return (
            f"{self.train} : "
            f"{self.gare_depart} -> {self.gare_arrivee} "
            f"({self.date_heure_depart:%d/%m %H:%M})"
        )


# ============================================================
# TARIF
# ============================================================

class Tarif(models.Model):
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    date_effet = models.DateField()

    date_fin = models.DateField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-date_effet"]

    def __str__(self):
        return (
            f"{self.montant} FCFA "
            f"a partir du {self.date_effet}"
        )


# ============================================================
# STATUT BILLET
# ============================================================

class StatutBillet(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    CONFIRME = "CONFIRME", "Confirme"
    ANNULE = "ANNULE", "Annule"


# ============================================================
# BILLET
# ============================================================

class Billet(models.Model):

    qr_code = models.CharField(
        max_length=255,
        unique=True
    )

    statut = models.CharField(
        max_length=15,
        choices=StatutBillet.choices,
        default=StatutBillet.EN_ATTENTE
    )

    date_achat = models.DateTimeField(
        auto_now_add=True
    )

    passager = models.ForeignKey(
        Passager,
        on_delete=models.CASCADE,
        related_name="billets"
    )

    voyage = models.ForeignKey(
        Voyage,
        on_delete=models.CASCADE,
        related_name="billets"
    )

    siege = models.ForeignKey(
        Siege,
        on_delete=models.PROTECT,
        related_name="billets"
    )

    tarif = models.ForeignKey(
        Tarif,
        on_delete=models.PROTECT,
        related_name="billets"
    )

    gare_embarquement = models.ForeignKey(
        Gare,
        on_delete=models.PROTECT,
        related_name="billets_embarquement",
        null=True,
        blank=True
    )

    gare_debarquement = models.ForeignKey(
        Gare,
        on_delete=models.PROTECT,
        related_name="billets_debarquement",
        null=True,
        blank=True
    )

    agent_gare = models.ForeignKey(
        AgentGare,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billets_vendus"
    )

    # Suppression "douce" : quand un passager supprime son billet, on ne
    # l'efface JAMAIS vraiment de la base (ca effacerait aussi le
    # Paiement associe en cascade, et donc la recette correspondante
    # des statistiques). On se contente de le masquer de sa liste. Les
    # statistiques (recettes, taux de remplissage...) portent sur TOUS
    # les billets confirmes, supprimes ou non - un achat reste un
    # achat, meme si le billet est ensuite supprime.
    supprime = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["voyage", "siege"],
                condition=models.Q(
                    statut__in=[
                        "EN_ATTENTE",
                        "CONFIRME"
                    ]
                ),
                name="unique_siege_par_voyage_actif",
            )
        ]

    def __str__(self):
        return (
            f"Billet {self.qr_code} - {self.passager}"
        )

    def heure_embarquement_calculee(self):
        if not self.gare_embarquement:
            return None

        return calculer_heure_passage(
            self.voyage,
            self.gare_embarquement
        )

    def heure_debarquement_calculee(self):
        if not self.gare_debarquement:
            return None

        return calculer_heure_passage(
            self.voyage,
            self.gare_debarquement
        )


# ============================================================
# METHODES DE PAIEMENT
# ============================================================

class MethodePaiement(models.TextChoices):
    ORANGE_MONEY = "ORANGE_MONEY", "Orange Money"
    WAVE = "WAVE", "Wave"
    GUICHET = "GUICHET", "Guichet"
    BORNE = "BORNE", "Borne automatique"


# ============================================================
# PAIEMENT
# ============================================================

class Paiement(models.Model):

    billet = models.OneToOneField(
        Billet,
        on_delete=models.CASCADE,
        related_name="paiement"
    )

    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    methode = models.CharField(
        max_length=15,
        choices=MethodePaiement.choices
    )

    date_paiement = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"Paiement {self.montant} FCFA "
            f"({self.get_methode_display()}) - "
            f"{self.billet}"
        )


# ============================================================
# FONCTIONS DE CALCUL DES HORAIRES
# ============================================================

def _gares_terminus():
    premiere = Gare.objects.order_by("ordre").first()
    derniere = Gare.objects.order_by("-ordre").first()
    return premiere, derniere


def _duree_par_segment():
    nb_gares = Gare.objects.count()

    if nb_gares < 2:
        raise ValueError(
            "Il faut au moins 2 gares creees "
            "pour planifier un voyage."
        )

    return DUREE_TRAJET_PAR_SEGMENT_MINUTES


def _temps_arret_avant_gare(voyage, gare):
    """
    Calcule le temps total passe a l'arret dans les gares
    intermediaires avant d'arriver a la gare demandee.
    """

    if gare is None:
        return 0

    if voyage.gare_depart.ordre < voyage.gare_arrivee.ordre:
        nombre_arrets = gare.ordre - voyage.gare_depart.ordre - 1
    else:
        nombre_arrets = voyage.gare_depart.ordre - gare.ordre - 1

    return max(0, nombre_arrets) * TEMPS_ARRET_GARE_MINUTES


def calculer_heure_passage(voyage, gare):
    """
    Calcule l'heure de passage du train dans une gare :
    5 minutes de trajet entre deux gares + 2 minutes d'arret
    dans chaque gare intermediaire traversee. Fonctionne dans
    les deux sens.
    """

    from datetime import timedelta

    if gare is None:
        return None

    duree_segment = _duree_par_segment()

    sens_croissant = (
        voyage.gare_depart.ordre
        < voyage.gare_arrivee.ordre
    )

    if sens_croissant:
        nombre_segments = gare.ordre - voyage.gare_depart.ordre
    else:
        nombre_segments = voyage.gare_depart.ordre - gare.ordre

    nombre_segments = max(0, nombre_segments)

    temps_trajet = nombre_segments * duree_segment
    temps_arret = _temps_arret_avant_gare(voyage, gare)
    temps_total = temps_trajet + temps_arret

    return voyage.date_heure_depart + timedelta(minutes=temps_total)


def _arrondir_au_creneau(dt, intervalle_minutes=INTERVALLE_DEPART_MINUTES):
    """
    Arrondit l'heure au creneau de depart INFERIEUR ou egal le
    plus proche (plancher, jamais vers le haut). Le voyage
    attribue au passager doit toujours etre a l'heure demandee
    ou avant, jamais apres.

    Exemple avec un intervalle de 10 minutes :

        14:01 -> 14:00
        14:06 -> 14:00
        14:09 -> 14:00
        14:10 -> 14:10
        14:16 -> 14:10
    """
    import math

    epoch_minutes = dt.timestamp() / 60
    plancher = math.floor(epoch_minutes / intervalle_minutes) * intervalle_minutes

    return dt.fromtimestamp(plancher * 60, tz=dt.tzinfo)


def obtenir_ou_creer_voyage(gare_embarquement, gare_debarquement, date_heure_souhaitee):
    """
    Trouve ou cree le voyage correspondant a la demande du
    passager : le systeme calcule automatiquement a quelle
    heure le train doit partir du terminus pour passer a la
    gare d'embarquement a l'heure demandee ou juste avant
    (jamais apres), arrets intermediaires de 2 minutes inclus.
    """

    from datetime import timedelta
    from django.utils import timezone

    if gare_embarquement.ordre == gare_debarquement.ordre:
        raise ValueError(
            "La gare de depart et d'arrivee "
            "doivent etre differentes."
        )

    sens_croissant = (
        gare_embarquement.ordre
        < gare_debarquement.ordre
    )

    premiere, derniere = _gares_terminus()

    if premiere is None or derniere is None:
        raise ValueError(
            "Impossible de determiner les gares terminus."
        )

    if sens_croissant:
        terminus_depart = premiere
        terminus_arrivee = derniere
    else:
        terminus_depart = derniere
        terminus_arrivee = premiere

    duree_segment = _duree_par_segment()

    if sens_croissant:
        nombre_segments = gare_embarquement.ordre - terminus_depart.ordre
    else:
        nombre_segments = terminus_depart.ordre - gare_embarquement.ordre

    nombre_segments = max(0, nombre_segments)

    temps_trajet = nombre_segments * duree_segment
    nombre_arrets = max(0, nombre_segments - 1)
    temps_arret = nombre_arrets * TEMPS_ARRET_GARE_MINUTES
    temps_avant_embarquement = temps_trajet + temps_arret

    depart_terminus_estime = (
        date_heure_souhaitee
        - timedelta(minutes=temps_avant_embarquement)
    )

    depart_terminus_arrondi = _arrondir_au_creneau(depart_terminus_estime)

    maintenant = timezone.now()
    while depart_terminus_arrondi < maintenant:
        depart_terminus_arrondi += timedelta(minutes=INTERVALLE_DEPART_MINUTES)

    nombre_segments_total = abs(terminus_arrivee.ordre - terminus_depart.ordre)
    nombre_arrets_total = max(0, nombre_segments_total - 1)
    duree_totale_voyage = (
        nombre_segments_total * duree_segment
        + nombre_arrets_total * TEMPS_ARRET_GARE_MINUTES
    )

    date_arrivee_terminus = (
        depart_terminus_arrondi
        + timedelta(minutes=duree_totale_voyage)
    )

    train = Train.objects.first()
    if train is None:
        raise ValueError(
            "Aucun train n'est enregistre - "
            "contactez l'administration."
        )

    voyage, cree = Voyage.objects.get_or_create(
        gare_depart=terminus_depart,
        gare_arrivee=terminus_arrivee,
        date_heure_depart=depart_terminus_arrondi,
        defaults={
            "train": train,
            "date_heure_arrivee": date_arrivee_terminus,
        }
    )

    heure_embarquement = calculer_heure_passage(voyage, gare_embarquement)
    heure_debarquement = calculer_heure_passage(voyage, gare_debarquement)

    return voyage, heure_embarquement, heure_debarquement


def nettoyer_voyages_passes_non_vendus():
    """Supprime les voyages termines qui n'ont aucun billet."""

    from django.db.models import Count
    from django.utils import timezone

    (
        Voyage.objects
        .filter(date_heure_arrivee__lt=timezone.now())
        .annotate(nb_billets=Count("billets"))
        .filter(nb_billets=0)
        .delete()
    )