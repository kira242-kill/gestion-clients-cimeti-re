from django.urls import path
from . import views, api
from django.conf import settings
from django.conf.urls.static import static

app_name = 'gestion'

urlpatterns = [
    # Pages HTML
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('render-section/<str:section>/', views.render_section, name='render_section'),
    path('logout/', views.logout_view, name='logout'),
    
    # API Ninja
    path("api/", api.api.urls), 
    
    # Actions (Gestion)
    path('update-tombe/<int:id>/', views.update_tombe, name='update_tombe'),
    path('download-recu/<int:id>/', views.download_recu_view, name='download-recu'),
    path('verification/<int:id>/', views.verification_scan, name='verification_scan'),
    path('add-user/', views.add_user_view, name='add_user'),

    # --- CORRECTION : Suppression du préfixe 'gestion/' redondant ---
    path('clients/', views.liste_clients, name='liste_clients'),
    path('clients/supprimer/<path:id>/', views.supprimer_client, name='supprimer_client'),

    # Portail Client
    path('client/portail/', views.portail_client, name='portail_client'),
    path('client/login/', views.client_login_view, name='client_login'), 
    path('client/register/', views.client_register_view, name='client_register'), # Ajoute aussi le register ici
    path('client/logout/', views.client_logout, name='client_logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)