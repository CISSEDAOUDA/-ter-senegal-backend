from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from comptes.models import Passager
from .models import Billet, ClasseWagon, Gare, Siege, Tarif, Train, Wagon, Voyage

Utilisateur = get_user_model()


class RechercheEtAchatTests(TestCase):
    def setUp(self):
        noms = ['Dakar','Colobane','Hann','Dalifort','Baux Maraichers','Pikine','Thiaroye','Diamaguene','Rufisque','Bargny','Diamniadio']
        for i, nom in enumerate(noms, start=1):
            Gare.objects.create(nom=nom, ordre=i)
        self.train = Train.objects.create(numero='TER-01')
        self.wagon = Wagon.objects.create(train=self.train, numero='W1', classe=ClasseWagon.PREMIERE)
        for n in ['1A', '1B', '1C']:
            Siege.objects.create(wagon=self.wagon, numero=n)
        Tarif.objects.create(montant=2500, date_effet=timezone.now().date())

        u = Utilisateur.objects.create_user(username='p1', password='x', email='p1@t.com', telephone='770000000')
        self.passager = Passager.objects.create(utilisateur=u, numero_piece_identite='CNI-1')
        self.client = APIClient()
        self.client.force_authenticate(user=u)

    def test_recherche_voyage_gares_intermediaires(self):
        hann = Gare.objects.get(nom='Hann')
        rufisque = Gare.objects.get(nom='Rufisque')
        souhait = timezone.now() + timedelta(hours=1)
        reponse = self.client.post('/api/billetterie/voyages/rechercher/', {
            'gare_embarquement_id': hann.id,
            'gare_debarquement_id': rufisque.id,
            'date_heure_souhaitee': souhait.isoformat(),
        }, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['voyage']['gare_depart']['nom'], 'Dakar')
        self.assertEqual(reponse.data['voyage']['gare_arrivee']['nom'], 'Diamniadio')

    def test_achat_avec_gares_intermediaires_bout_en_bout(self):
        hann = Gare.objects.get(nom='Hann')
        rufisque = Gare.objects.get(nom='Rufisque')
        souhait = timezone.now() + timedelta(hours=2)
        reponse = self.client.post('/api/billetterie/achat/', {
            'passager_id': self.passager.id,
            'gare_embarquement_id': hann.id,
            'gare_debarquement_id': rufisque.id,
            'date_heure_souhaitee': souhait.isoformat(),
            'siege_id': Siege.objects.first().id,
            'methode_paiement': 'GUICHET',
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertEqual(reponse.data['gare_embarquement']['nom'], 'Hann')
        self.assertEqual(reponse.data['gare_debarquement']['nom'], 'Rufisque')
        self.assertEqual(reponse.data['statut'], 'CONFIRME')
        self.assertIsNotNone(reponse.data['heure_embarquement'])

    def test_deux_achats_meme_creneau_reutilisent_le_meme_voyage(self):
        """Deux recherches proches dans le temps doivent tomber sur le meme Voyage (pas de doublon)."""
        dakar = Gare.objects.get(nom='Dakar')
        diamniadio = Gare.objects.get(nom='Diamniadio')
        base = timezone.now() + timedelta(hours=3)
        r1 = self.client.post('/api/billetterie/voyages/rechercher/', {
            'gare_embarquement_id': dakar.id, 'gare_debarquement_id': diamniadio.id,
            'date_heure_souhaitee': base.isoformat(),
        }, format='json')
        r2 = self.client.post('/api/billetterie/voyages/rechercher/', {
            'gare_embarquement_id': dakar.id, 'gare_debarquement_id': diamniadio.id,
            'date_heure_souhaitee': (base + timedelta(minutes=2)).isoformat(),
        }, format='json')
        self.assertEqual(r1.data['voyage']['id'], r2.data['voyage']['id'])
        self.assertEqual(Voyage.objects.count(), 1)

    def test_gare_depart_egale_arrivee_refusee(self):
        dakar = Gare.objects.get(nom='Dakar')
        reponse = self.client.post('/api/billetterie/voyages/rechercher/', {
            'gare_embarquement_id': dakar.id, 'gare_debarquement_id': dakar.id,
            'date_heure_souhaitee': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(reponse.status_code, 400)


class StatistiquesTests(TestCase):
    def setUp(self):
        noms = ['Dakar','Colobane','Hann','Dalifort','Baux Maraichers','Pikine','Thiaroye','Diamaguene','Rufisque','Bargny','Diamniadio']
        for i, nom in enumerate(noms, start=1):
            Gare.objects.create(nom=nom, ordre=i)
        self.train = Train.objects.create(numero='TER-01')
        self.wagon = Wagon.objects.create(train=self.train, numero='W1', classe=ClasseWagon.PREMIERE)
        for n in ['1A', '1B', '1C', '1D']:
            Siege.objects.create(wagon=self.wagon, numero=n)
        self.tarif = Tarif.objects.create(montant=2500, date_effet=timezone.now().date())

        u_admin = Utilisateur.objects.create_user(username='admin1', password='x', email='a@t.com', telephone='770000000')
        from comptes.models import Administrateur
        Administrateur.objects.create(utilisateur=u_admin, matricule='ADM-1')
        self.client = APIClient()
        self.client.force_authenticate(user=u_admin)

        u1 = Utilisateur.objects.create_user(username='pax1', password='x', email='p1@t.com', telephone='770000001')
        self.p1 = Passager.objects.create(utilisateur=u1, numero_piece_identite='CNI-1')
        u2 = Utilisateur.objects.create_user(username='pax2', password='x', email='p2@t.com', telephone='770000002')
        self.p2 = Passager.objects.create(utilisateur=u2, numero_piece_identite='CNI-2')

    def _acheter(self, passager, gare_emb, gare_deb, siege, methode='GUICHET'):
        client = APIClient()
        client.force_authenticate(user=passager.utilisateur)
        souhait = timezone.now() + timedelta(hours=2)
        return client.post('/api/billetterie/achat/', {
            'passager_id': passager.id, 'gare_embarquement_id': gare_emb.id,
            'gare_debarquement_id': gare_deb.id, 'date_heure_souhaitee': souhait.isoformat(),
            'siege_id': siege.id, 'methode_paiement': methode,
        }, format='json')

    def test_recettes_par_gare_et_par_methode(self):
        dakar = Gare.objects.get(nom='Dakar')
        hann = Gare.objects.get(nom='Hann')
        diamniadio = Gare.objects.get(nom='Diamniadio')
        sieges = list(Siege.objects.all())

        r1 = self._acheter(self.p1, dakar, diamniadio, sieges[0], methode='GUICHET')
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self._acheter(self.p2, hann, diamniadio, sieges[1], methode='ORANGE_MONEY')
        self.assertEqual(r2.status_code, 201, r2.content)

        reponse = self.client.get('/api/billetterie/statistiques/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        data = reponse.data

        gares_recettes = {g['gare']: g['montant_total'] for g in data['recettes_par_gare']}
        self.assertEqual(gares_recettes.get('Dakar'), 2500.0)
        self.assertEqual(gares_recettes.get('Hann'), 2500.0)

        methodes = {m['methode']: m['montant_total'] for m in data['recettes_par_methode']}
        self.assertEqual(methodes.get('GUICHET'), 2500.0)
        self.assertEqual(methodes.get('ORANGE_MONEY'), 2500.0)

        self.assertIsNotNone(data['taux_remplissage_moyen_pourcentage'])
        print('  taux de remplissage moyen:', data['taux_remplissage_moyen_pourcentage'], '%')


class ArrondiVoyagePlancherTests(TestCase):
    """Le voyage attribue doit toujours etre <= a l'heure demandee (jamais apres)."""
    def setUp(self):
        noms = ['Dakar','Colobane','Hann','Dalifort','Baux Maraichers','Pikine','Thiaroye','Diamaguene','Rufisque','Bargny','Diamniadio']
        for i, nom in enumerate(noms, start=1):
            Gare.objects.create(nom=nom, ordre=i)
        Train.objects.create(numero='TER-01')

    def test_voyage_jamais_apres_heure_souhaitee(self):
        from billetterie.models import obtenir_ou_creer_voyage
        dakar = Gare.objects.get(nom='Dakar')
        diamniadio = Gare.objects.get(nom='Diamniadio')
        for minutes_offset in [1, 4, 9, 11, 19, 23, 30, 37, 59]:
            base = (timezone.now() + timedelta(hours=2)).replace(second=0, microsecond=0)
            base = base.replace(minute=(base.minute // 10) * 10)
            souhait = base + timedelta(minutes=minutes_offset)
            voyage, h_emb, h_deb = obtenir_ou_creer_voyage(dakar, diamniadio, souhait)
            self.assertLessEqual(h_emb, souhait, f"voyage {h_emb} est APRES le souhait {souhait}")
            ecart = (souhait - h_emb).total_seconds() / 60
            self.assertLess(ecart, 10, f"ecart trop grand : {ecart} min")


class SuppressionBilletTests(TestCase):
    def setUp(self):
        noms = ['Dakar','Colobane','Hann','Dalifort','Baux Maraichers','Pikine','Thiaroye','Diamaguene','Rufisque','Bargny','Diamniadio']
        for i, nom in enumerate(noms, start=1):
            Gare.objects.create(nom=nom, ordre=i)
        train = Train.objects.create(numero='TER-01')
        wagon = Wagon.objects.create(train=train, numero='W1', classe=ClasseWagon.PREMIERE)
        self.sieges = [Siege.objects.create(wagon=wagon, numero=n) for n in ['1A', '1B']]
        Tarif.objects.create(montant=2500, date_effet=timezone.now().date())

        u1 = Utilisateur.objects.create_user(username='pax1', password='x', email='p1@t.com', telephone='770000001')
        self.p1 = Passager.objects.create(utilisateur=u1, numero_piece_identite='CNI-1')
        u2 = Utilisateur.objects.create_user(username='pax2', password='x', email='p2@t.com', telephone='770000002')
        self.p2 = Passager.objects.create(utilisateur=u2, numero_piece_identite='CNI-2')

    def _acheter(self, passager, siege):
        client = APIClient()
        client.force_authenticate(user=passager.utilisateur)
        dakar = Gare.objects.get(nom='Dakar')
        diamniadio = Gare.objects.get(nom='Diamniadio')
        souhait = timezone.now() + timedelta(hours=2)
        return client.post('/api/billetterie/achat/', {
            'passager_id': passager.id, 'gare_embarquement_id': dakar.id,
            'gare_debarquement_id': diamniadio.id, 'date_heure_souhaitee': souhait.isoformat(),
            'siege_id': siege.id, 'methode_paiement': 'GUICHET',
        }, format='json')

    def test_suppression_billet_non_valide_autorisee(self):
        reponse_achat = self._acheter(self.p1, self.sieges[0])
        self.assertEqual(reponse_achat.status_code, 201)
        billet_id = reponse_achat.data['id']
        self.assertEqual(reponse_achat.data['statut'], 'CONFIRME')  # confirme mais jamais scanne

        client = APIClient()
        client.force_authenticate(user=self.p1.utilisateur)
        reponse_suppr = client.delete(f'/api/billetterie/billets/{billet_id}/')
        self.assertEqual(reponse_suppr.status_code, 204, reponse_suppr.content)
        # Suppression douce : le billet n'est PAS efface de la base
        # (pour preserver le paiement/les statistiques), il est juste
        # marque supprime et masque de la liste du passager.
        billet = Billet.objects.get(id=billet_id)
        self.assertTrue(billet.supprime)
        reponse_liste = client.get('/api/billetterie/billets/')
        self.assertEqual(len(reponse_liste.data), 0)

    def test_impossible_de_supprimer_le_billet_dun_autre_passager(self):
        reponse_achat = self._acheter(self.p1, self.sieges[1])
        billet_id = reponse_achat.data['id']

        client_p2 = APIClient()
        client_p2.force_authenticate(user=self.p2.utilisateur)
        reponse = client_p2.delete(f'/api/billetterie/billets/{billet_id}/')
        self.assertEqual(reponse.status_code, 404)  # invisible dans son propre queryset
        self.assertTrue(Billet.objects.filter(id=billet_id).exists())


class SuppressionDouceStatistiquesTests(TestCase):
    """Un billet supprime doit disparaitre de la liste du passager
    MAIS rester comptabilise dans les statistiques de recettes."""

    def setUp(self):
        noms = ['Dakar','Colobane','Hann','Dalifort','Baux Maraichers','Pikine','Thiaroye','Diamaguene','Rufisque','Bargny','Diamniadio']
        for i, nom in enumerate(noms, start=1):
            Gare.objects.create(nom=nom, ordre=i)
        train = Train.objects.create(numero='TER-01')
        wagon = Wagon.objects.create(train=train, numero='W1', classe=ClasseWagon.PREMIERE)
        self.siege = Siege.objects.create(wagon=wagon, numero='1A')
        Tarif.objects.create(montant=2500, date_effet=timezone.now().date())

        u_admin = Utilisateur.objects.create_user(username='admin1', password='x', email='a@t.com', telephone='770000000')
        from comptes.models import Administrateur
        Administrateur.objects.create(utilisateur=u_admin, matricule='ADM-1')
        self.client_admin = APIClient()
        self.client_admin.force_authenticate(user=u_admin)

        u1 = Utilisateur.objects.create_user(username='pax1', password='x', email='p1@t.com', telephone='770000001')
        self.p1 = Passager.objects.create(utilisateur=u1, numero_piece_identite='CNI-1')

    def test_recettes_inchangees_apres_suppression(self):
        dakar = Gare.objects.get(nom='Dakar')
        diamniadio = Gare.objects.get(nom='Diamniadio')
        client_p1 = APIClient()
        client_p1.force_authenticate(user=self.p1.utilisateur)

        souhait = timezone.now() + timedelta(hours=2)
        reponse_achat = client_p1.post('/api/billetterie/achat/', {
            'passager_id': self.p1.id, 'gare_embarquement_id': dakar.id,
            'gare_debarquement_id': diamniadio.id, 'date_heure_souhaitee': souhait.isoformat(),
            'siege_id': self.siege.id, 'methode_paiement': 'GUICHET',
        }, format='json')
        self.assertEqual(reponse_achat.status_code, 201, reponse_achat.content)
        billet_id = reponse_achat.data['id']

        stats_avant = self.client_admin.get('/api/billetterie/statistiques/').data
        recette_avant = sum(g['montant_total'] for g in stats_avant['recettes_par_gare'])
        self.assertEqual(recette_avant, 2500.0)

        # Suppression par le passager
        reponse_suppr = client_p1.delete(f'/api/billetterie/billets/{billet_id}/')
        self.assertEqual(reponse_suppr.status_code, 204, reponse_suppr.content)

        # Le billet a disparu de SA liste
        reponse_liste = client_p1.get('/api/billetterie/billets/')
        self.assertEqual(len(reponse_liste.data), 0)

        # Mais la recette est TOUJOURS comptabilisee
        stats_apres = self.client_admin.get('/api/billetterie/statistiques/').data
        recette_apres = sum(g['montant_total'] for g in stats_apres['recettes_par_gare'])
        self.assertEqual(recette_apres, 2500.0, "la recette ne doit PAS disparaitre apres suppression du billet")

        # Le billet existe toujours reellement en base (supprime=True, pas efface)
        billet = Billet.objects.get(id=billet_id)
        self.assertTrue(billet.supprime)
        self.assertTrue(hasattr(billet, 'paiement'))  # le paiement existe toujours