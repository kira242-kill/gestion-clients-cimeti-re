from django.db import models
from django.contrib.auth.models import User


class ClientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telephone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.user.username
class Zone(models.Model):
    nom_zone = models.CharField(max_length=100)
    code_zone = models.CharField(max_length=10, unique=True)
    superficie = models.FloatField(help_text="Superficie totale en m²")
    longueur = models.FloatField()  # en mètres
    largeur = models.FloatField()

    def __str__(self):
        return self.nom_zone

class Tombe(models.Model):
    numero_tombe = models.CharField(max_length=50)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="tombes")
    
    STATUT_CHOICES = [
        ('Disponible', 'Disponible'),
        ('Réservée', 'Réservée'),
        ('Occupée', 'Occupée'),
        ('NonExploitable', 'Zone non exploitable'),
    ]
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='Disponible')
    
    localisation = models.CharField(max_length=255, null=True, blank=True)
    coordonnee_x = models.FloatField() 
    coordonnee_y = models.FloatField()

    def __str__(self):
        return f"Tombe {self.numero_tombe} ({self.zone.nom_zone})"
    
    @property
    def est_disponible(self):
        return self.statut == 'Disponible'


class Defunt(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_enterrement = models.DateField()
    tombe = models.OneToOneField(Tombe, on_delete=models.CASCADE, related_name="defunt")

class Demande(models.Model):
    email_client = models.EmailField()
    nom_defunt_prevu = models.CharField(max_length=100)
    prenom_defunt_prevu = models.CharField(max_length=100)
    date_enterrement = models.DateField(null=True, blank=True)
    
    montant_devis = models.DecimalField(max_digits=10, decimal_places=2, default=0) 
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # statut_demande: 'En attente', 'Devis envoyé', 'Payé', 'Approuvé', 'Rejeté'
    statut_demande = models.CharField(max_length=20, default='En attente')
    
    tombe = models.ForeignKey(Tombe, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    devis_pdf = models.FileField(upload_to='documents/devis/', null=True, blank=True)
    recu_pdf = models.FileField(upload_to='documents/recus/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

class HistoriqueAction(models.Model):
    agent = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    date_action = models.DateTimeField(auto_now_add=True)
    details = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.agent.username} - {self.action}"


