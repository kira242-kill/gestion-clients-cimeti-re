from django.contrib import admin
from django.urls import path, include
from gestion import views  # <-- Importe tes vues ici
from gestion.api import api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('gestion/', include('gestion.urls')),
    
    # Appel direct de la vue index
    path('', views.index, name='index'), 
]