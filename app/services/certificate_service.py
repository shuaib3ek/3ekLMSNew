import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor

def generate_workshop_certificate(learner_name, workshop_title, completion_date):
    """
    Generates a PDF certificate in memory using ReportLab.
    """
    buffer = io.BytesIO()
    
    # Setup the page in landscape
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # 1. Background / Border
    p.setStrokeColor(HexColor('#6366f1'))  # 3EK Primary
    p.setLineWidth(5)
    p.rect(0.5*inch, 0.5*inch, width - 1*inch, height - 1*inch)
    
    p.setStrokeColor(HexColor('#e2e8f0'))  # Border secondary
    p.setLineWidth(1)
    p.rect(0.6*inch, 0.6*inch, width - 1.2*inch, height - 1.2*inch)

    # 2. Header / Logo Placeholder
    p.setFillColor(HexColor('#6366f1'))
    p.setFont("Helvetica-Bold", 40)
    p.drawCentredString(width/2, height - 2*inch, "CERTIFICATE")
    
    p.setFillColor(HexColor('#0f172a'))
    p.setFont("Helvetica", 20)
    p.drawCentredString(width/2, height - 2.5*inch, "OF COMPLETION")

    # 3. Content
    p.setFont("Helvetica", 16)
    p.drawCentredString(width/2, height - 3.5*inch, "This is to certify that")
    
    p.setFillColor(HexColor('#6366f1'))
    p.setFont("Helvetica-Bold", 32)
    p.drawCentredString(width/2, height - 4.2*inch, learner_name.upper())

    p.setFillColor(HexColor('#0f172a'))
    p.setFont("Helvetica", 16)
    p.drawCentredString(width/2, height - 5*inch, "has successfully completed the workshop")
    
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(width/2, height - 5.6*inch, f'"{workshop_title}"')

    # 4. Footer
    p.setFont("Helvetica", 12)
    date_str = completion_date.strftime('%d %B, %Y') if isinstance(completion_date, datetime) else str(completion_date)
    p.drawString(1.5*inch, 1.5*inch, f"Date: {date_str}")
    
    # 3EK Signature line
    p.line(width - 3*inch, 1.5*inch, width - 1*inch, 1.5*inch)
    p.drawCentredString(width - 2*inch, 1.3*inch, "Authorized Signatory")
    p.drawCentredString(width - 2*inch, 1.1*inch, "3rd Eye Knowledge")

    # Save
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer
