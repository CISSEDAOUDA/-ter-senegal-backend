from django.contrib import admin

from .models import Billet, Gare, Paiement, Siege, Tarif, Train, Voyage, Wagon

admin.site.register(Gare)
admin.site.register(Train)
admin.site.register(Wagon)
admin.site.register(Siege)
admin.site.register(Voyage)
admin.site.register(Tarif)
admin.site.register(Billet)
admin.site.register(Paiement)
