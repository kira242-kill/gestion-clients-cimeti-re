from django.contrib import admin
from .models import Zone, Tombe, Defunt, Demande


# Configuration de la Zone
@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('nom_zone', 'code_zone', 'superficie')
    search_fields = ('nom_zone', 'code_zone')

# Configuration de la Tombe
@admin.register(Tombe)
class TombeAdmin(admin.ModelAdmin):
    list_display = ('numero_tombe', 'zone', 'statut')
    list_filter = ('statut', 'zone')
    search_fields = ('numero_tombe',)

# Configuration du Défunt
@admin.register(Defunt)
class DefuntAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'date_enterrement', 'tombe')
    search_fields = ('nom', 'prenom')

# Configuration de la Demande
@admin.register(Demande)
class DemandeAdmin(admin.ModelAdmin):
    list_display = ('email_client', 'nom_defunt_prevu', 'statut_demande', 'date_creation')
    list_filter = ('statut_demande',)
    search_fields = ('email_client', 'nom_defunt_prevu')