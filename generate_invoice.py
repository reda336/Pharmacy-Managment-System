from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from io import BytesIO
import pandas as pd
import os
import json
from datetime import datetime, date
from sqlalchemy import extract, func

# PDF
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

def generate_invoice(order):

    os.makedirs("invoices", exist_ok=True)

    filename = f"invoices/invoice_{order.invoice_number}.pdf"

    c = canvas.Canvas(filename, pagesize=A4)

    c.setFont("Helvetica-Bold",16)
    c.drawString(20*mm,280*mm,"Pharmacy Invoice")

    c.setFont("Helvetica",12)

    c.drawString(20*mm,260*mm,f"Invoice : {order.invoice_number}")
    c.drawString(20*mm,250*mm,f"Date : {order.created_at.strftime('%Y-%m-%d')}")

    if order.user:
        c.drawString(20*mm,230*mm,f"Customer : {order.user.name}")
        c.drawString(20*mm,220*mm,f"Phone : {order.user.phone}")

    y = 200*mm

    if order.drug:
        c.drawString(20*mm,y,f"Drug : {order.drug.name}")
        c.drawString(100*mm,y,f"Qty : {order.quantity}")
        c.drawString(140*mm,y,f"Price : {order.drug.price}")

        total = order.quantity * float(order.drug.price)

        c.drawString(20*mm,y-20,f"Total : {total}")

    c.save()

    return filename
