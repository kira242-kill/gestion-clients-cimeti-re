from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from gestion.api import api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    
    # Toutes les routes de gestion commencent par /gestion/
    path('gestion/', include('gestion.urls')),
    
    # La racine redirige vers le dashboard (qui est maintenant sous /gestion/dashboard/)
    path('', lambda request: redirect('gestion:dashboard')), 
]