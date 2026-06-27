from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.security import HttpBearer
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login, logout
from typing import Optional
from .models import Demande, Tombe, Zone, Defunt, HistoriqueAction
from .utils import generer_document_pdf, envoyer_document_par_mail, enregistrer_action
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from datetime import datetime, date
from pydantic import Field, EmailStr
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


# 1. Classe d'authentification étendue
class GlobalAuth(HttpBearer):
    def authenticate(self, request, token):
        # Vérification Agent (Utilisateur Django authentifié)
        if request.user.is_authenticated:
            return request.user
        
        # Vérification Client (Email présent en session)
        if request.session.get('email_client'):
            return request.session.get('email_client')
            
        return None

# 2. Initialisation avec la nouvelle sécurité
api = NinjaAPI(auth=GlobalAuth())
# --- SCHÉMAS ---
class AmenagementSchema(Schema):
    nom_zone: str
    zone_l: float
    zone_w: float
    caveau_l: float
    allee: float

class ZoneSchema(Schema):
    nom_zone: str
    code_zone: str
    superficie: float

class ZoneOut(Schema):
    id: int
    nom_zone: str
    code_zone: str
    superficie: float

class TombeOut(Schema):
    id: int
    numero_tombe: str
    statut: str
    zone_id: int
    coordonnee_x: Optional[float] = None  
    coordonnee_y: Optional[float] = None 
    nom_defunt: Optional[str] = None

class DemandeSchema(Schema):
    email_client: EmailStr
    nom_defunt_prevu: str = Field(..., max_length=100)
    prenom_defunt_prevu: str = Field(..., max_length=100)
    date_enterrement: date
    tombe_id: int

class DemandeOut(Schema):
    id: int
    email_client: str
    nom_defunt_prevu: str
    prenom_defunt_prevu: str
    date_creation: str
    numero_tombe: str

class LoginSchema(Schema):
    username: str
    password: str

class HistoriqueOut(Schema):
    date_action: str
    agent: str
    action: str
    details: str


# --- API PUBLIQUES (auth=None) ---
@api.get("/historique", response=list[HistoriqueOut], auth=None)
def lister_historique(request):
    actions = HistoriqueAction.objects.all().order_by('-date_action')
    return [{"date_action": a.date_action.strftime("%d/%m/%Y %H:%M"), "agent": a.agent.username if a.agent else "Système", "action": a.action, "details": a.details} for a in actions]

@api.get("/zones", response=list[ZoneOut], auth=None)
def lister_zones(request):
    return Zone.objects.all()

@api.get("/tombes", response=list[TombeOut], auth=None)
def lister_tombes(request, statut: Optional[str] = None, zone_id: Optional[int] = None):
    qs = Tombe.objects.all()
    if statut:
        qs = qs.filter(statut=statut)
    if zone_id:
        qs = qs.filter(zone_id=zone_id)
    res = []
    for t in qs:
        defunt_nom = f"{t.defunt.nom} {t.defunt.prenom}" if hasattr(t, 'defunt') and t.defunt else "Libre"
        res.append({"id": t.id, "numero_tombe": t.numero_tombe, "statut": t.statut, "zone_id": t.zone_id, "coordonnee_x": t.coordonnee_x, "coordonnee_y": t.coordonnee_y, "nom_defunt": defunt_nom})
    return res

@api.post("/login", auth=None)
def login_agent(request, data: LoginSchema):
    user = authenticate(username=data.username, password=data.password)
    if user:
        login(request, user)
        return {"message": "Connexion réussie !"}
    raise HttpError(401, "Identifiants invalides")

@api.get("/stats-globales/", auth=None)
def stats_globales(request):
    return {"dispo": Tombe.objects.filter(statut='Disponible').count(), "occupe": Tombe.objects.filter(statut='Occupée').count(), "demandes": Demande.objects.filter(statut_demande='En attente').count()}

@api.post("/tombes/{tombe_id}/statut", auth=None)
def changer_statut_tombe(request, tombe_id: int, nouveau_statut: str):
    t = get_object_or_404(Tombe, id=tombe_id)
    t.statut = nouveau_statut
    t.save()
    return {"message": "Statut mis à jour."}

@api.get("/stats/tombes", auth=None)
def obtenir_stats_tombes(request):
    return list(Tombe.objects.values('statut').annotate(total=Count('statut')))

@api.get("/utilisateurs/", auth=None) 
def lister_utilisateurs(request):
    return [{"username": u.username, "email": u.email} for u in User.objects.all()]

@api.get("/demandes/{demande_id}/telecharger-devis", auth=None)
def telecharger_devis(request, demande_id: int):
    d = get_object_or_404(Demande, id=demande_id)
    pdf = generer_document_pdf(d, type_doc="DEVIS")
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="devis_{d.id}.pdf"'
    return resp

# --- API PROTÉGÉES (auth=AuthBearer par défaut) ---

@api.post("/creer-demande", auth=None)
def creer_demande(request, data: DemandeSchema):
    t = get_object_or_404(Tombe, id=data.tombe_id)
    if t.statut != 'Disponible':
        raise HttpError(400, "Indisponible")
    
    # 1. On ne crée l'utilisateur que s'il n'existe pas, sans bloquer la demande
    user, created = User.objects.get_or_create(
        username=data.email_client, 
        defaults={'email': data.email_client}
    )
    
    # 2. Création de la demande sans condition d'existence préalable
    d = Demande.objects.create(
        email_client=data.email_client, 
        nom_defunt_prevu=data.nom_defunt_prevu, 
        prenom_defunt_prevu=data.prenom_defunt_prevu, 
        date_enterrement=data.date_enterrement, 
        tombe=t, 
        statut_demande='En attente'
    )
    
    t.statut = 'Réservée'
    t.save()
    return {"message": "Réservation enregistrée"}


@api.get("/demandes", response=list[dict], auth=None) # Change list[DemandeOut] par list[dict] pour plus de souplesse
def lister_demandes(request):
    # On récupère les données avec les relations nécessaires
    demandes = Demande.objects.filter(statut_demande='En attente')
    res = []
    for d in demandes:
        res.append({
            "id": d.id,
            "email_client": d.email_client,
            "numero_tombe": d.tombe.numero_tombe, # Assure que ce champ existe
            "date_creation": d.date_creation.strftime("%d/%m/%Y") if d.date_creation else "N/A"
        })
    return res

from django.db import transaction
from ninja.errors import HttpError

@csrf_exempt
@api.post("/demandes/{demande_id}/traiter", auth=None)
def traiter_demande(request, demande_id: int, action: str):
    d = get_object_or_404(Demande, id=demande_id)
    
    # 1. Utilisation d'une transaction atomique : 
    # Tout réussit, ou rien n'est modifié en base.
    try:
        with transaction.atomic():
            if action == "Approuvée":
                Defunt.objects.create(
                    nom=d.nom_defunt_prevu, 
                    prenom=d.prenom_defunt_prevu, 
                    date_enterrement=d.date_creation, 
                    tombe=d.tombe
                )
                d.statut_demande = "Approuvée"
                d.tombe.statut = "Occupée"
            elif action == "Rejetée":
                d.statut_demande = "Rejetée"
                d.tombe.statut = "Disponible"
            else:
                raise HttpError(400, "Action non reconnue")
            
            d.tombe.save()
            d.save()
            
            # Gestion sécurisée de l'agent
            agent = request.user if request.user.is_authenticated else None
            enregistrer_action(agent, action, f"Demande {d.id} {action}")

        # 2. Envoi de l'email HORS de la transaction
        # Si l'email échoue, la DB reste propre car la transaction est déjà validée
        if action == "Approuvée":
            # On appelle la nouvelle fonction API Brevo (non bloquante)
            envoyer_document_par_mail(d, type_doc="REÇU")
            
        return {"message": f"{action} avec succès"}

    except Exception as e:
        logger.error(f"Erreur lors du traitement de la demande {demande_id}: {e}")
        raise HttpError(500, "Erreur interne lors du traitement")

@api.post("/zones", auth=None)
def creer_zone(request, data: ZoneSchema):
    z = Zone.objects.create(**data.dict())
    return {"id": z.id, "message": "Succès"}

@api.post("/logout")
def logout_agent(request):
    logout(request)
    return {"message": "Déconnexion réussie"}

@api.post("/generer-tombes/", auth=None)
def generer_tombes(request, data: AmenagementSchema):
    nouvelle_zone = Zone.objects.create(
        nom_zone=data.nom_zone,
        code_zone=f"{data.nom_zone[0:2].upper()}{Zone.objects.count() + 1}",
        superficie=data.zone_l * data.zone_w,
        longueur=data.zone_l,
        largeur=data.zone_w
    )
    
    surface_par_tombe = data.caveau_l * (data.caveau_l + data.allee)
    nombre_tombes = int((data.zone_l * data.zone_w) / surface_par_tombe)
    
    # Paramètres de base pour la grille
    start_lat = -4.75329
    start_lon = 11.93913
    cols = 10 # Nombre de tombes par ligne
    
    for i in range(1, nombre_tombes + 1):
        numero = f"{nouvelle_zone.code_zone}-{str(i).zfill(3)}"

        # Calcul automatique des coordonnées (espacement de 0.0001 degré)
        row = i // cols
        col = i % cols

        Tombe.objects.create(
            numero_tombe=numero,
            statut="Disponible",
            zone=nouvelle_zone,
            coordonnee_x=start_lon + (col * 0.0001),
            coordonnee_y=start_lat - (row * 0.0001)
        )

    return {"status": "success", "message": f"Zone '{data.nom_zone}' créée avec {nombre_tombes} tombes !"}

@api.delete("/zones/{zone_id}")
def supprimer_zone(request, zone_id: int):
    get_object_or_404(Zone, id=zone_id).delete()
    return {"message": "Supprimé"}

@api.post("/tombes/{tombe_id}/attribuer")
def attribuer_tombe(request, tombe_id: int, nom: str, prenom: str, date_ent: str):
    t = get_object_or_404(Tombe, id=tombe_id)
    d_obj = datetime.strptime(date_ent, '%Y-%m-%d').date()
    Defunt.objects.create(nom=nom, prenom=prenom, date_enterrement=d_obj, tombe=t)
    t.statut = "Occupée"
    t.save()
    return {"message": "Attribué"}

@api.post("/demandes/{demande_id}/confirmer-paiement")
def confirmer_paiement(request, demande_id: int):
    d = get_object_or_404(Demande, id=demande_id)
    d.statut_paiement = "Payé"
    d.save()
    envoyer_document_par_mail(d, type_doc="REÇU")
    enregistrer_action(request.user, "Paiement", f"Paiement pour {d.id}")
    return {"message": "Confirmé"}

@api.post("/demandes/{demande_id}/envoyer-devis")
def envoyer_devis(request, demande_id: int, montant: float):
    d = get_object_or_404(Demande, id=demande_id)
    d.montant_devis = montant
    d.statut_demande = "Devis envoyé"
    d.save()
    envoyer_document_par_mail(d, type_doc="DEVIS")
    enregistrer_action(request.user, "Devis", f"Devis pour {d.id}")
    return {"message": "Envoyé"}

@api.delete("/supprimer-demande/{demande_id}")
def supprimer_demande(request, demande_id: int):
    d = get_object_or_404(Demande, id=demande_id)
    if not (request.user.is_authenticated or request.session.get('email_client') == d.email_client):
        raise HttpError(403, "Refusé")
    d.tombe.statut = 'Disponible'
    d.tombe.save()
    d.delete()
    return {"message": "Supprimé"}

@api.exception_handler(Exception)
def on_error(request, exc):
    return api.create_response(request, {"message": str(exc)}, status=500)