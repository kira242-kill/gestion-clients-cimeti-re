from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Demande
from .utils import generer_document_pdf, envoyer_email_otp
from django.http import JsonResponse
from .models import Zone, Tombe
import json
import math
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.db import transaction
from .models import HistoriqueAction
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
import random
from django.core.mail import send_mail
from django.conf import settings

def index(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('gestion:dashboard')
        return redirect('gestion:portail_client')
    
    # Indique le chemin relatif complet au dossier templates
    return render(request, 'core/home.html')

# On vérifie que seul l'agent peut voir cette liste
@user_passes_test(lambda u: u.is_staff)
def liste_clients(request):
    # On récupère tous les utilisateurs qui ne sont pas administrateurs
    clients = User.objects.filter(is_staff=False, is_superuser=False)
    return render(request, 'gestion/liste_clients.html', {'clients': clients})

@user_passes_test(lambda u: u.is_staff)
def supprimer_client(request, id):
    # 'id' est maintenant l'email (ex: 'kirarider0@gmail.com')
    # Utilise .filter pour éviter les erreurs si l'email n'existe pas
    Demande.objects.filter(email_client=id).update(is_active=False)
    return redirect('gestion:render_section', section='gestion_clients')

def client_register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Compte créé avec succès !")
            return redirect('gestion:client_login')
    else:
        form = UserCreationForm()

    return render(request, 'client/register.html', {'form': form})
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index') # Assure-toi que 'index' est bien le nom de ta page
    else:
        form = UserCreationForm()
    return render(request, 'core/login.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def dashboard_view(request):
    return render(request, 'gestion/dashboard.html')

def api_cartographie(request):
    tombes = Tombe.objects.all().values('id', 'numero_tombe', 'statut', 'coordonnee_x', 'coordonnee_y')
    return JsonResponse(list(tombes), safe=False)
    
@login_required
def download_recu_view(request, id):
    demande = get_object_or_404(Demande, id=id)
    # On utilise la nouvelle fonction avec type_doc="REÇU"
    pdf_content = generer_document_pdf(demande, type_doc="REÇU") 
    
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recu_{demande.id}.pdf"'
    return response

def verification_scan(request, id=None):
    demande = None
    # Si on a un ID via le QR Code, on cherche
    if id:
        demande = get_object_or_404(Demande, id=id)
    
    # Si l'agent fait une recherche manuelle par numéro de tombe
    if request.method == "POST":
        num = request.POST.get('numero_tombe')
        demande = Demande.objects.filter(tombe__numero_tombe=num).first()
        
    return render(request, 'gestion/verification.html', {'demande': demande})

def render_section(request, section):
    # Dictionnaire des sections disponibles
    sections = {
        'dashboard_home': 'sections/dashboard_home.html',
        'cartographie': 'sections/cartographie.html',
        'utilisateurs': 'sections/utilisateurs.html',
        'gestion_clients': 'gestion/liste_clients.html',
        'liste_clients': 'gestion/liste_clients.html',
        'amenagement': 'sections/amenagement.html',
        'parametres': 'sections/parametres.html',
        'tombes': 'sections/tombes.html',
        'demandes': 'sections/demandes.html',
        'historique': 'gestion/historique.html',
    }

    # Vérification de l'existence de la section
    template = sections.get(section)
    if not template:
        return HttpResponse("Section non trouvée", status=404)

    # Initialisation du contexte
    context = {}

    if section == 'demandes':
        context['demandes'] = Demande.objects.all().order_by('-id')

    # Logique spécifique pour chaque section nécessitant des données dynamiques
    if section in ['liste_clients', 'gestion_clients']:
        # Dans render_section, pour la section liste_clients
        emails = Demande.objects.filter(is_active=True).values_list('email_client', flat=True).distinct()

        clients = []
        for email in emails:
            clients.append({
                'id': email,
                'username': email.split('@')[0], 
                'email': email
            })
        context['clients'] = clients

    if section == 'historique':
        context['actions'] = HistoriqueAction.objects.all().order_by('-date_action')

    return render(request, template, context)


def mettre_a_jour_statuts_automatique():
    # Trouve toutes les tombes réservées dont la date d'enterrement est aujourd'hui ou passée
    today = timezone.now().date()
    tombes_a_occuper = Tombe.objects.filter(
        statut='Réservée', 
        defunt__date_enterrement__lte=today
    )
    for tombe in tombes_a_occuper:
        tombe.statut = 'Occupée'
        tombe.save()


# 1. Déconnexion pour les AGENTS (Admin/Staff)
def logout_view(request):
    logout(request)  # Déconnecte uniquement l'utilisateur Django
    return redirect('gestion:login')

# 2. Déconnexion pour les CLIENTS (Portail)
def client_logout(request):
    logout(request)  # Au cas où un client aurait aussi un compte Django
    request.session.flush()  # Nettoie TOUT (email_client + autres variables)
    return redirect('gestion:client_login')

@login_required
def api_tombes(request):
    # 1. Mise à jour automatique des statuts avant de renvoyer les données
    today = timezone.now().date()
    
    # On passe les tombes réservées en "Occupée" si la date est arrivée
    Tombe.objects.filter(
        statut='Réservée', 
        defunt__date_enterrement__lte=today
    ).update(statut='Occupée')
    
    # 2. Récupération des données
    tombes = Tombe.objects.all().values('id', 'numero_tombe', 'statut')
    return JsonResponse(list(tombes), safe=False)

def api_stats_globales(request):
    data = {
        'dispo': Tombe.objects.filter(statut='Disponible').count(),
        'occupe': Tombe.objects.filter(statut='Occupée').count(),
        'demandes': Demande.objects.filter(statut_demande='En attente').count()
    }
    return JsonResponse(data)

@login_required
@transaction.atomic
def generer_tombes(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Récupération des données du formulaire pro
            zone_l = float(data.get('zone_l'))
            zone_w = float(data.get('zone_w'))
            caveau_l = float(data.get('caveau_l'))
            caveau_w = float(data.get('caveau_w'))
            allee = float(data.get('allee'))

            # Calcul du nombre de tombes
            nb_lignes = math.floor(zone_l / (caveau_l + allee))
            nb_cols = math.floor(zone_w / (caveau_w + allee))

            marge_x = (zone_w - (nb_cols * (caveau_w + allee))) / 2
            marge_y = (zone_l - (nb_lignes * (caveau_l + allee))) / 2

            for i in range(nb_lignes):
                for j in range(nb_cols):
                    Tombe.objects.create(
                        numero_tombe=f"T-{i+1}-{j+1}",
                        coordonnee_x=round(marge_x + (j * (caveau_w + allee)), 2),
                        coordonnee_y=round(marge_y + (i * (caveau_l + allee)), 2),
                        statut='Disponible'
                    )
            return JsonResponse({'status': 'success', 'message': f'{nb_lignes * nb_cols} tombes générées avec succès.'})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)


@login_required
def add_user_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', '')
            )
            return JsonResponse({'status': 'success', 'message': 'Utilisateur ajouté !'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)

def update_tombe(request, id):
    if request.method == 'POST':
        try:
            # Récupérer les données envoyées par JavaScript
            data = json.loads(request.body)
            # Trouver la tombe dans la base de données
            tombe = get_object_or_404(Tombe, id=id)
            # Modifier le statut
            tombe.statut = data['statut']
            tombe.save()
            return JsonResponse({'status': 'success', 'message': 'Statut mis à jour'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)

def demande_tombe_view(request):
    # On récupère les tombes pour le menu déroulant
    tombes = Tombe.objects.filter(statut='Disponible')
    return render(request, 'client/base_client.html', {'section_template': 'client/sections/demande.html'})


@login_required
def historique_view(request):
    actions = HistoriqueAction.objects.all().order_by('-date_action')
    
    # Filtres simples
    date_filter = request.GET.get('date')
    if date_filter:
        actions = actions.filter(date_action__date=date_filter)
        
    return render(request, 'gestion/historique.html', {'actions': actions})

def portail_client(request):
    # 1. Protection : Si la section est 'suivi', on vérifie l'authentification
    section = request.GET.get('section', 'accueil')
    if section == 'suivi' and 'email_client' not in request.session:
        # Remplace 'gestion:client_login' par le nom de ta route de login client
        return redirect('gestion:client_login') 

    sections = {
        'accueil': 'client/sections/accueil.html',
        'demande': 'client/sections/demande.html',
        'suivi': 'client/sections/suivi.html'
    }
    
    # Initialisation du contexte
    context = {
        'section_template': sections.get(section, 'client/sections/accueil.html'),
        'section': section 
    }
    
    # Récupération des tombes pour la demande
    if section == 'demande':
        context['tombes'] = Tombe.objects.filter(statut='Disponible')
    
    # Gestion du suivi avec protection par session
    if section == 'suivi':
        user_email = request.session.get('email_client')
        context['demandes'] = Demande.objects.filter(email_client=user_email).order_by('-date_creation')
    
    return render(request, 'client/base_client.html', context)

def login_page(request):
    return render(request, 'core/login.html')

def client_login_view(request):
    """
    Vue de connexion client par OTP avec gestion stricte de la session.
    """
    # Debug pour vérifier que les paramètres SMTP sont bien lus par le serveur
    print(f"DEBUG_SMTP: Host={settings.EMAIL_HOST}, User={settings.EMAIL_HOST_USER}, Pwd_len={len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 0}")
    
    if request.method == 'POST':
        # 1. PRIORITÉ : Vérification du code OTP (Étape 2)
        if 'code' in request.POST:
            user_code = request.POST.get('code', '').strip()
            stored_code = request.session.get('otp_code')
            
            # Debug : Permet de voir précisément ce qui bloque dans les logs Render
            print(f"DEBUG_OTP: Code Saisi='{user_code}', Code Session='{stored_code}'")
            print(f"DEBUG_SESSION: Session ID={request.session.session_key}")
            
            # Comparaison sécurisée (converti en str pour éviter les erreurs de type)
            if stored_code and str(user_code) == str(stored_code):
                # Succès : on connecte le client
                request.session['email_client'] = request.session.get('temp_email')
                
                # Nettoyage propre de la session
                request.session.pop('otp_code', None)
                request.session.pop('temp_email', None)
                request.session.modified = True
                
                return redirect('gestion:portail_client')
            else:
                messages.error(request, "Code invalide ou expiré. Veuillez réessayer.")
                return render(request, 'client/login_otp.html')

        # 2. ÉTAPE 1 : Soumission de l'email
        elif 'email' in request.POST:
            email = request.POST.get('email', '').strip().lower()
            
            if not email:
                messages.error(request, "Veuillez entrer une adresse email valide.")
                return render(request, 'client/login.html')

            # Génération d'un nouveau code
            code = str(random.randint(100000, 999999))
            
            # Stockage en session
            request.session['temp_email'] = email
            request.session['otp_code'] = code
            request.session.modified = True  # Force la sauvegarde du cookie de session
            
            print(f"DEBUG: Session mise à jour. Email={email}, Code={code}")
            
            # Envoi de l'email
            try:
                envoyer_email_otp(email, code)
                print("Succès : Email envoyé via API/SMTP")
                messages.success(request, "Un code de validation vous a été envoyé par email.")
                return render(request, 'client/login_otp.html')
            except Exception as e:
                print(f"ERREUR_EMAIL: {str(e)}")
                messages.error(request, "Erreur lors de l'envoi de l'email. Veuillez réessayer.")
                return render(request, 'client/login.html')
    
    # Cas GET : affichage initial
    return render(request, 'client/login.html')