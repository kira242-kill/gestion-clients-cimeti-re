import os
import django

# Configure Django pour pouvoir utiliser les modèles
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth.models import User

# Remplace par tes identifiants voulus
username = 'mpenhy'
password = 'mpenhy//2000'
email = 'kirarider0@gmail.com'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, password=password, email=email)
    print(f"Superuser '{username}' créé avec succès.")
else:
    print("Le superuser existe déjà.")