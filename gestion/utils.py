from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from django.core.mail import EmailMessage
import qrcode
from io import BytesIO
from .models import HistoriqueAction
from django.core.files.base import ContentFile
from reportlab.lib.utils import ImageReader
from django.core.mail import send_mail
import logging
from django.conf import settings
import socket
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import base64
import os


logger = logging.getLogger(__name__)

def generer_document_pdf(demande, type_doc="REÇU"):
    buffer = BytesIO()
    qr_stream = BytesIO()
    
    try:
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # 1. Ajout du Logo (depuis ton dossier static)
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
        if os.path.exists(logo_path):
            p.drawImage(logo_path, 50, height - 100, width=80, height=80, preserveAspectRatio=True)

        p.setTitle(f"Reçu {demande.id}")  
        p.setAuthor("Gestion Cimetière")  
        p.setSubject("Document officiel de confirmation")

        # 2. En-tête coloré et stylisé
        p.setFillColor(colors.darkblue)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(150, height - 70, f"DOCUMENT : {type_doc.upper()}")
        
        p.setStrokeColor(colors.darkblue)
        p.setLineWidth(2)
        p.line(50, height - 120, 550, height - 120)

        # 3. Détails avec couleurs
        y = height - 180
        p.setFillColor(colors.black)
        p.setFont("Helvetica", 12)
        
        montant = demande.montant_devis if type_doc == "DEVIS" else demande.montant_paye
        
        details = [
            ("Demandeur :", demande.email_client),
            ("Nom du défunt :", f"{demande.nom_defunt_prevu} {demande.prenom_defunt_prevu}"),
            ("Tombe N° :", str(demande.tombe.numero_tombe)),
            ("Date souhaitée :", str(demande.date_enterrement)),
            ("Montant total :", f"{montant} FCFA")
        ]
        
        for label, val in details:
            p.setFont("Helvetica-Bold", 12)
            p.drawString(100, y, label)
            p.setFont("Helvetica", 12)
            p.drawString(250, y, val)
            y -= 30

        # 4. QR Code
        qr_data = f"ID_DEMANDE:{demande.id}"
        qr = qrcode.make(qr_data)
        qr.save(qr_stream, format="PNG")
        qr_stream.seek(0)
        p.drawImage(ImageReader(qr_stream), 400, 100, width=100, height=100)
        
        p.showPage()
        p.save()

        pdf_data = buffer.getvalue()
        
        # Sauvegarde modèle
        filename = f"{type_doc.lower()}_{demande.id}.pdf"
        if type_doc == "DEVIS": demande.devis_pdf.save(filename, ContentFile(pdf_data), save=True)
        else: demande.recu_pdf.save(filename, ContentFile(pdf_data), save=True)
        
        return pdf_data
    finally:
        buffer.close()
        qr_stream.close()

def envoyer_document_par_mail(demande, type_doc="REÇU"):
    try:
        # Générer le PDF
        pdf_content = generer_document_pdf(demande, type_doc=type_doc)
        
        # Préparer l'API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.EMAIL_HOST_PASSWORD
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        # Encodage Base64 du PDF
        encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": demande.email_client}],
            sender={"name": "Gestion Cimetière", "email": "kirarider0@gmail.com"},
            subject=f'{type_doc} pour votre demande - G_C',
            html_content = f"""<div style="font-family: sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #2c3e50;">Gestion Cimetière - Votre document</h2>
                    <p>Bonjour,</p>
                    <p>Veuillez trouver ci-joint le <strong>{type_doc}</strong> officiel concernant votre demande N°{demande.id}.</p>
                    <p>Ce document est une pièce justificative officielle. Merci de le conserver précieusement.</p>
                    <hr>
                    <p style="font-size: 0.9em; color: #777;">Ceci est un envoi automatique de la plateforme Gestion Cimetière.</p>
                </div>
                """
            attachment=[{"name": f"Reçu_Demande_{demande.id}_Gestion_Cimetiere.pdf", "content": encoded_pdf}]
        )
        
        api_instance.send_transac_email(send_smtp_email)
        logger.info("Email envoyé avec succès via API.")
        
    except ApiException as e:
        logger.error(f"Erreur API Brevo: {e}")
    except Exception as e:
        logger.error(f"Erreur fatale envoi email: {e}")

def enregistrer_action(user, action, details):
    HistoriqueAction.objects.create(agent=user, action=action, details=details)

def envoyer_email_otp(email, code):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = settings.EMAIL_HOST_PASSWORD 
    
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    subject = "Votre code de vérification"
    html_content = f"<html><body>Votre code OTP est : <strong>{code}</strong></body></html>"
    # IMPORTANT : l'email ici doit être celui validé sur Brevo
    sender = {"name": "Gestion Cimetière", "email": "kirarider0@gmail.com"} 
    to = [{"email": email}]
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=html_content, sender=sender, subject=subject)
    
    try:
        api_instance.send_transac_email(send_smtp_email)
        print("Succès : Email envoyé via API")
    except ApiException as e:
        print(f"Erreur API Brevo: {e}")