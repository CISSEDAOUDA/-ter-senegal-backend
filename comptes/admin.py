from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Administrateur, AgentGare, ChefTrain, Controleur, Passager, Utilisateur


class UtilisateurAdmin(DjangoUserAdmin):
    """
    Etend l'admin Django standard (qui hache correctement les mots de
    passe via UserCreationForm) pour notre champ telephone en plus.
    Ne PAS utiliser admin.ModelAdmin basique ici : il enregistrerait le
    mot de passe en clair, rendant le compte impossible a authentifier.
    """
    model = Utilisateur
    fieldsets = DjangoUserAdmin.fieldsets + (
        (None, {"fields": ("telephone",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (None, {"fields": ("telephone", "email")}),
    )
    list_display = ["username", "email", "first_name", "last_name", "is_staff"]


admin.site.register(Utilisateur, UtilisateurAdmin)
admin.site.register(Passager)
admin.site.register(Administrateur)
admin.site.register(Controleur)
admin.site.register(AgentGare)
admin.site.register(ChefTrain)
