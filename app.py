from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from dotenv import load_dotenv
import smtplib
import os
import io
from email.message import EmailMessage

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///donations.db'
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'change_this_default_secret')
db = SQLAlchemy(app)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    animal_type = db.Column(db.String(20))
    meat_lbs = db.Column(db.String(20))
    city = db.Column(db.String(100))
    delivery_type = db.Column(db.String(50))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route("/", methods=["GET", "POST"])
def donate():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        animal_type = request.form.get("animal_type")
        meat_lbs = request.form.get("meat_lbs")
        city = request.form.get("city")
        delivery_type = "Masjid Ibrahim"

        if not phone:
            flash("Phone number is required!", "danger")
            return redirect(url_for("donate"))

        donation = Donation(
            name=name,
            phone=phone,
            email=email,
            animal_type=animal_type,
            meat_lbs=meat_lbs,
            city=city,
            delivery_type=delivery_type
        )
        db.session.add(donation)
        db.session.commit()

        if email:
            send_email_confirmation(email, name, animal_type, meat_lbs)

        flash("Thank you for your donation!", "success")
        return redirect(url_for("donate"))

    return render_template("donate.html")

def send_email_confirmation(email, name, animal_type, meat_lbs):
    subject = "Thank You for Your Meat Donation!"
    body = f"""Dear {name},

Thank you for your generous donation of {meat_lbs} lbs of {animal_type.lower()} meat. Your contribution will be distributed via Masjid Ibrahim's local recipient pairing system.

JazakAllah Khair for your support!

— The Meat Donation Service Team
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Email failed:", e)

@app.route("/dashboard")
def dashboard():
    donations = Donation.query.all()
    total_lbs = sum([float(d.meat_lbs.replace('lbs', '').strip()) for d in donations if d.meat_lbs])
    total_donors = len(donations)

    by_animal = {}
    for d in donations:
        key = d.animal_type or "Unknown"
        by_animal[key] = by_animal.get(key, 0) + float(d.meat_lbs.replace('lbs', '').strip())

    labels = list(by_animal.keys())
    data = list(by_animal.values())

    return render_template("dashboard.html", total_lbs=total_lbs, total_donors=total_donors, labels=labels, data=data)

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("admin_login.html")

@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    donations = Donation.query.all()
    return render_template("admin.html", donations=donations)

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/export_pdf")
def export_pdf():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    donations = Donation.query.all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    data = [["Name", "Phone", "Email", "Animal", "Meat(lbs)", "City", "Delivery Type"]]
    for d in donations:
        data.append([
            d.name, d.phone, d.email or "", d.animal_type, d.meat_lbs + " lbs", d.city, d.delivery_type
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    doc.build([table])
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="donations.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))