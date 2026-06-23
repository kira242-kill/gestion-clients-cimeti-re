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

logger = logging.getLogger(__name__)

def generer_document_pdf(demande, type_doc="REÇU"):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # 1. En-tête
    p.setFont("Helvetica-Bold", 20)
    p.drawString(200, height - 80, type_doc.upper())

    p.setStrokeColor(colors.gray)
    p.line(50, height - 120, 550, height - 120)

    # 2. Détails dynamiques
    p.setFont("Helvetica", 12)
    y = height - 160
    
    montant = demande.montant_devis if type_doc == "DEVIS" else demande.montant_paye
    
    details = [
        f"Demandeur : {demande.email_client}",
        f"Nom du défunt : {demande.nom_defunt_prevu}",
        f"Prénom du défunt : {demande.prenom_defunt_prevu}",
        f"Tombe N° : {demande.tombe.numero_tombe}",
        f"Date souhaitée : {demande.date_enterrement}",
        f"Montant ({type_doc}) : {montant} FCFA"
    ]
    
    for line in details:
        p.drawString(100, y, line)
        y -= 25

    # 3. QR Code intégré
    qr_data = f"ID_DEMANDE:{demande.id}"
    qr = qrcode.make(qr_data)
    qr_stream = BytesIO()
    qr.save(qr_stream, format="PNG")
    qr_stream.seek(0)
    
    # CORRECTION : Utilisation de ImageReader pour lire le flux BytesIO
    qr_image = ImageReader(qr_stream)
    p.drawImage(qr_image, 400, y - 100, width=100, height=100)
    
    # 4. Pied de page
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(100, 50, "Document généré par le système G_C.")
    
    # Finalisation du document
    p.showPage()
    p.save()

    # Récupération sécurisée du contenu final
    pdf_data = buffer.getvalue()
    buffer.close()
    qr_stream.close() # Nettoyage du flux QR

    # Sauvegarde dans le modèle
    filename = f"{type_doc.lower()}_{demande.id}.pdf"
    if type_doc == "DEVIS":
        demande.devis_pdf.save(filename, ContentFile(pdf_data), save=True)
    else:
        demande.recu_pdf.save(filename, ContentFile(pdf_data), save=True)

    return pdf_data


def envoyer_document_par_mail(demande, type_doc="REÇU"):
    pdf_content = generer_document_pdf(demande, type_doc=type_doc)
    
    email = EmailMessage(
        f'{type_doc} pour votre demande - G_C',
        f'Veuillez trouver ci-joint votre {type_doc} concernant la tombe {demande.tombe.numero_tombe}.',
        'gestion@cimetiere.com',
        [demande.email_client],
    )
    email.attach(f'{type_doc.lower()}_{demande.id}.pdf', pdf_content, 'application/pdf')
    email.send()

def enregistrer_action(user, action, details):
    HistoriqueAction.objects.create(agent=user, action=action, details=details)


def envoyer_email_otp(email, code):
    try:
        subject = 'Votre code de vérification'
        message = f'Votre code OTP est : {code}'
        from_email = 'ton_email@gmail.com' # Doit correspondre à EMAIL_HOST_USER
        
        # On met fail_silently=True pour éviter le crash du serveur
        send_mail(subject, message, from_email, [email], fail_silently=True)
    except Exception as e:
        logger.error(f"Erreur envoi email: {e}")