
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash,check_password_hash
from io import BytesIO
import pandas as pd
import os
import json
from datetime import datetime, date
from sqlalchemy import extract, func
from openpyxl import Workbook
from collections import defaultdict
# PDF
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4


# ================= APP =================


app = Flask(__name__)
app.secret_key = "pharmacy_secret_999"

uri = os.environ.get("DATABASE_URL", "sqlite:///pharmacy.db")

if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ================= MODELS =================


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(200))

    orders = db.relationship("Order", backref="user")


class Pharmacist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    pharmacy_name = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=False)
    address = db.Column(db.String(255))
   


    drugs = db.relationship("Drug", backref="pharmacist")
    orders = db.relationship("Order", backref="pharmacist")
    supply_requests = db.relationship("SupplyRequest", backref="pharmacist")


class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))
    price = db.Column(db.String(50))
    quantity = db.Column(db.Integer)
    available = db.Column(db.Boolean, default=True)

    pharmacist_id = db.Column(db.Integer, db.ForeignKey("pharmacist.id"))




class Order(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    # ===== معلومات الطلب =====
    quantity = db.Column(db.Integer, default=1)

    # 🔥 السعرات المالية
    total_price = db.Column(db.Float, default=0)
    delivery_fee = db.Column(db.Float, default=0)

    # ===== حالة الطلب =====
    status = db.Column(db.String(100), default="قيد الانتظار")
    seen = db.Column(db.Boolean, default=False)

    # ===== التوصيل أو الاستلام =====
    delivery_type = db.Column(
        db.String(50),
        default="استلام"
    )

    address = db.Column(
        db.String(300),
        nullable=True
    )

    # ===== الفاتورة =====
    invoice_number = db.Column(
        db.Integer,
        unique=True
    )

    # ===== التتبع والوقت =====
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # ===== العلاقات =====
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )
    user_phone=db.Column(db.String(20))
    drug_id = db.Column(
        db.Integer,
        db.ForeignKey("drug.id")
    )

    pharmacist_id = db.Column(
        db.Integer,
        db.ForeignKey("pharmacist.id")
    )

    drug = db.relationship("Drug")
    payment_method=db.Column(db.String(20))
    

class SupplyRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    drug_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))

    status = db.Column(db.String(100), default="قيد المراجعة")

    pharmacist_id = db.Column(db.Integer, db.ForeignKey("pharmacist.id"))

    provided_by = db.Column(db.String(200))
    provided_price = db.Column(db.String(100))

    # 🔥 روابط ذكية للتتبع
    new_drug_id = db.Column(db.Integer, db.ForeignKey("drug.id"))
    user_notified = db.Column(db.Boolean, default=False)


with app.app_context():
    db.create_all()

# ================= HOME =================

from flask import request, render_template, session
from sqlalchemy import and_

@app.route("/", methods=["GET"])
def index():
    # ===== البحث عن دواء =====
    search = request.form.get("search")  # لأن النموذج POST

    if search:
        drugs = Drug.query.filter(
            and_(Drug.name.contains(search), Drug.available==True)
        ).all()
        not_found = len(drugs) == 0
    else:
        drugs = Drug.query.filter_by(available=True).all()
        not_found = False

    # ===== بيانات الجلسة =====
    user_name = session.get("user_name")
    user_id = session.get("user_id")

    # ===== إشعارات الصيدلي =====
    notifications_orders = 0
    notifications_supply = 0
    if "pharmacist_id" in session:
        pharmacist_id = session["pharmacist_id"]
        notifications_orders = Order.query.filter_by(
            pharmacist_id=pharmacist_id, seen=False
        ).count()
        notifications_supply = SupplyRequest.query.filter_by(
            pharmacist_id=pharmacist_id, status="pending"
        ).count()

    return render_template(
        "index.html",
        drugs=drugs,
        search=search,
        not_found=not_found,
        notifications_orders=notifications_orders,
        notifications_supply=notifications_supply,
        user_name=user_name,
        user_id=user_id
    )

# ================= DOWNLOAD INVOICE =================

@app.route("/download_invoice/<int:order_id>")
def download_invoice(order_id):

    order = Order.query.get_or_404(order_id)

    filename = f"invoice_{order.invoice_number}.pdf"

    return send_from_directory("invoices", filename)


@app.route("/payment/<int:order_id>", methods=["GET", "POST"])
def online_payment(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == "POST":
        # عملية الدفع ناجحة
        order.status = "قيد الانتظار"  # يمكن تعديل حسب النظام
        db.session.commit()
        flash("✅ تم الدفع بنجاح")
        return redirect(url_for("track_order"))

    return render_template("online_payment.html", order=order)

@app.route("/request_supply", methods=["POST"])
def request_supply():

    drug_name = request.form.get("drug_name")
    phone = request.form.get("phone")

    pharmacists = Pharmacist.query.filter_by(approved=True).all()

    for p in pharmacists:

        req = SupplyRequest(
            drug_name=drug_name,
            phone=phone,
            pharmacist_id=p.id
        )

        db.session.add(req)

    db.session.commit()

    flash("تم إرسال طلب التوفير للصيدليات")
    return redirect(url_for("index"))


# ================= TRACK SUPPLY =================
@app.route("/track_supply", methods=["GET","POST"])
def track_supply():

    requests = None

    if request.method == "POST":

        phone = request.form.get("phone")

        requests = SupplyRequest.query.filter_by(phone=phone).all()

    return render_template("track_supply.html", requests=requests)


@app.route("/provide_supply", methods=["POST"])
def provide_supply():

    if "pharmacist_id" not in session:
        return redirect(url_for("login"))

    req = SupplyRequest.query.get(request.form.get("request_id"))
    price = request.form.get("price")

    if req:

        pharmacist = Pharmacist.query.get(req.pharmacist_id)

        # 🔥 إنشاء الدواء داخل قائمة الصيدليات
        drug = Drug(
            name=req.drug_name,
            price=price,
            quantity=10,
            pharmacist_id=req.pharmacist_id,
            available=True
        )

        db.session.add(drug)

        req.status = "تم توفير الدواء ✔"
        req.provided_by = pharmacist.pharmacy_name
        req.provided_price = price

        db.session.commit()

        flash("✅ تم توفير الدواء")

    return redirect(url_for("index"))

@app.route("/supply_requests")
def supply_requests():

    if "pharmacist_id" not in session:
        return redirect(url_for("login"))

    requests = SupplyRequest.query.filter_by(
        pharmacist_id=session["pharmacist_id"]
    ).all()

    return render_template(
        "supply_requests.html",
        requests=requests
    )

@app.route("/update_pharmacy_location/<int:pharmacy_id>", methods=["GET", "POST"])
def update_pharmacy_location(pharmacy_id):
    pharmacy = Pharmacist.query.get_or_404(pharmacy_id)

    if request.method == "POST":
        try:
            Pharmacist.latitude = float(request.form.get("latitude"))
            Pharmacist.longitude = float(request.form.get("longitude"))
            db.session.commit()
            flash("تم تحديث الموقع بنجاح!", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash("حدث خطأ أثناء حفظ الموقع.", "danger")

    return render_template("update_pharmacy_location.html", Pharmacist=Pharmacist)




@app.route("/register_pharmacist", methods=["GET", "POST"])
def register_pharmacist():
    if request.method == "POST":
        # جلب البيانات من النموذج
        email = request.form.get("email")
        pharmacy_name = request.form.get("pharmacy_name")
        address = request.form.get("address","").strip()

        # التحقق من اكتمال البيانات
        if not all([email, pharmacy_name, address]):
            flash("❌ أكمل جميع الحقول", "danger")
            return redirect(url_for("register_pharmacist"))

        # إنشاء الصيدلية في قاعدة البيانات (غير معتمد بشكل افتراضي)
        new_pharmacy = Pharmacist(
            email=email,
            pharmacy_name=pharmacy_name,
            address=address,
            approved=False  # يتم الاعتماد لاحقًا من قبل الادمن
        )

        db.session.add(new_pharmacy)
        db.session.commit()

        flash("✅ تم إرسال طلب الاعتماد للادمن")
        return redirect(url_for("index"))

    # إذا GET، عرض النموذج
    return render_template("register_pharmacist.html")


# ================= Pharmacist Login =================

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")

        p = Pharmacist.query.filter_by(
            email=email,
            approved=True
        ).first()

        if p:
            session["pharmacist_id"] = p.id
            return redirect(url_for("pharmacist"))

        flash("غير معتمد أو البريد غير صحيح")

    return render_template("login.html")



@app.route("/pharmacist", methods=["GET","POST"])
def pharmacist():

    if "pharmacist_id" not in session:
        return redirect(url_for("login"))

    pharmacist = Pharmacist.query.get(session.get("pharmacist_id"))

    if not pharmacist:
        session.pop("pharmacist_id", None)
        return redirect(url_for("login"))

    drugs_to_display = []

    # ===== إضافة دواء =====
    if request.method == "POST":

        name = request.form.get("name").strip()
        price = request.form.get("price").strip()
        quantity = request.form.get("quantity").strip()

        if not name or not price or not quantity:
            flash("أكمل جميع البيانات", "warning")
            return redirect(url_for("pharmacist"))

        try:
            quantity = int(quantity)
            price = float(price)
        except ValueError:
            flash("السعر أو الكمية غير صحيحة", "warning")
            return redirect(url_for("pharmacist"))

        existing_drug = Drug.query.filter_by(
            name=name,
            pharmacist_id=pharmacist.id
        ).first()

        # منع تكرار الدواء
        if existing_drug:
            drugs_to_display = [existing_drug]
            flash("⚠ هذا الدواء موجود مسبقًا، يمكنك تعديله من الجدول", "warning")

        else:
            new_drug = Drug(
                name=name,
                price=price,
                quantity=quantity,
                pharmacist_id=pharmacist.id,
                available=True
            )

            db.session.add(new_drug)
            db.session.commit()

            drugs_to_display = [new_drug]
            flash("✅ تم إضافة الدواء بنجاح", "success")

    # ===== البحث عن دواء =====
    search = request.args.get("search")

    if search:
        drugs_to_display = Drug.query.filter(
            Drug.pharmacist_id == pharmacist.id,
            Drug.name.contains(search)
        ).all()

    # ===== عرض كل الأدوية إذا لا يوجد بحث =====
    if not drugs_to_display and not search:
        drugs_to_display = Drug.query.filter_by(
            pharmacist_id=pharmacist.id
        ).all()

    # ===== إشعارات الطلبات =====
    notifications_orders = Order.query.filter_by(
        pharmacist_id=pharmacist.id,
        seen=False
    ).count()

    # ===== إشعارات طلبات التوفير =====
    notifications_supply = SupplyRequest.query.filter_by(
        status="قيد المراجعة"
    ).count()

    return render_template(
        "pharmacist.html",
        drugs=drugs_to_display,
        search=search,
        notifications_orders=notifications_orders,
        notifications_supply=notifications_supply
    )


# ================= Pharmacist Orders =================

@app.route("/pharmacist_orders")
def pharmacist_orders():

    if "pharmacist_id" not in session:
        return redirect(url_for("login"))

    pharmacist = Pharmacist.query.get(session["pharmacist_id"])

    orders = pharmacist.orders

    for o in orders:
        o.seen = True

    db.session.commit()

    return render_template("pharmacist_orders.html", orders=orders)

@app.route("/approve_pharmacist", methods=["POST"])
def approve_pharmacist():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    pharmacist_id = request.form.get("pharmacist_id")
    action = request.form.get("action")

    pharmacist = Pharmacist.query.get(pharmacist_id)

    if pharmacist:

        if action == "approve":
            pharmacist.approved = True
        elif action == "reject":
            db.session.delete(pharmacist)  # أو تخليه False حسب رغبتك

        db.session.commit()

    return redirect(url_for("admin_dashboard"))

@app.route("/update_drug", methods=["POST"])
def update_drug():

    if "pharmacist_id" not in session:
        return redirect(url_for("login"))

    drug = Drug.query.get(request.form.get("drug_id"))

    if drug:
        drug.quantity = int(request.form.get("quantity"))
        db.session.commit()

    return redirect(url_for("pharmacist"))

@app.route("/reports")
def reports():

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    orders = Order.query.all()

    if start_date and end_date:

        start = datetime.strptime(start_date,"%Y-%m-%d")
        end = datetime.strptime(end_date,"%Y-%m-%d")

        orders = [
            o for o in orders
            if start <= o.created_at <= end
        ]

    total_orders = len(orders)
    total_revenue = sum(o.total_price for o in orders)

    today = datetime.today().date()

    today_revenue = sum(
        o.total_price for o in orders
        if o.created_at.date() == today
    )

    month_revenue = sum(
        o.total_price for o in orders
        if o.created_at.month == today.month
    )

    year_revenue = sum(
        o.total_price for o in orders
        if o.created_at.year == today.year
    )

    daily_revenue = defaultdict(float)
    monthly_revenue = defaultdict(float)
    yearly_revenue = defaultdict(float)

    drug_sales = defaultdict(int)

    for o in orders:

        day = o.created_at.strftime("%Y-%m-%d")
        month = o.created_at.strftime("%Y-%m")
        year = o.created_at.strftime("%Y")

        daily_revenue[day] += o.total_price
        monthly_revenue[month] += o.total_price
        yearly_revenue[year] += o.total_price

        drug_sales[o.drug.name] += o.quantity

    top_drugs = sorted(
        drug_sales.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    return render_template(

        "reports.html",

        total_orders=total_orders,
        total_revenue=total_revenue,
        today_revenue=today_revenue,
        month_revenue=month_revenue,
        year_revenue=year_revenue,

        daily_labels=list(daily_revenue.keys()),
        daily_data=list(daily_revenue.values()),

        monthly_labels=list(monthly_revenue.keys()),
        monthly_data=list(monthly_revenue.values()),

        yearly_labels=list(yearly_revenue.keys()),
        yearly_data=list(yearly_revenue.values()),

        drug_labels=[d[0] for d in top_drugs],
        drug_data=[d[1] for d in top_drugs]
    )


@app.route("/export_excel")
def export_excel():

    orders = Order.query.all()

    wb = Workbook()
    ws = wb.active

    ws.append([
        "Order ID",
        "Customer",
        "Drug",
        "Quantity",
        "Total Price",
        "Date"
    ])

    for o in orders:

        ws.append([
            o.id,
            o.user.name if o.user else "",
            o.drug.name if o.drug else "",
            o.quantity,
            o.total_price,
            o.created_at.strftime("%Y-%m-%d")
        ])

    os.makedirs("reports", exist_ok=True)

    filename = "reports/pharmacy_report.xlsx"

    wb.save(filename)




    return send_file(filename, as_attachment=True)


@app.route("/delete_drug", methods=["POST"])
def delete_drug():

    if "pharmacist_id" not in session:
        return redirect(url_for("login"))

    drug = Drug.query.get(request.form.get("drug_id"))

    if drug:
        db.session.delete(drug)
        db.session.commit()

    return redirect(url_for("pharmacist"))


@app.route("/order", methods=["POST"])
def new_order():

    # ===== التحقق من تسجيل الدخول =====
    phone = session.get("user_phone")

    if not phone:
        flash("❌ الرجاء تسجيل الدخول أولاً", "danger")
        return redirect(url_for("login_user"))

    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("❌ المستخدم غير موجود", "danger")
        return redirect(url_for("login_user"))

    # ===== جلب البيانات =====
    drug_id = request.form.get("drug_id")
    name = request.form.get("name")
    quantity = request.form.get("quantity")
    delivery_type = request.form.get("delivery_type")
    address = request.form.get("address")
    payment_method = request.form.get("payment_method")

    if not all([drug_id, name, quantity, delivery_type]):
        flash("أكمل جميع البيانات")
        return redirect(url_for("index"))

    try:
        drug_id = int(drug_id)
        qty = int(quantity)
    except:
        flash("البيانات غير صحيحة")
        return redirect(url_for("index"))

    # ===== جلب الدواء =====
    drug = Drug.query.get(drug_id)

    if not drug:
        flash("الدواء غير موجود")
        return redirect(url_for("index"))

    drug_quantity = int(drug.quantity)

    if qty <= 0 or qty > drug_quantity:
        flash("الكمية غير متوفرة")
        return redirect(url_for("index"))

    # ===== حساب السعر =====
    unit_price = float(drug.price)
    total_price = qty * unit_price

    delivery_fee = 0

    if delivery_type == "توصيل":

        if not address:
            flash("أدخل العنوان للتوصيل")
            return redirect(url_for("index"))

        delivery_fee = 2000

    total_price += delivery_fee

    # ===== إنشاء رقم الفاتورة =====
    last_invoice = Order.query.order_by(Order.invoice_number.desc()).first()

    if last_invoice and last_invoice.invoice_number:
        invoice_number = int(last_invoice.invoice_number) + 1
    else:
        invoice_number = 1000

    # ===== خصم المخزون =====
    drug.quantity = drug_quantity - qty

    # ===== إنشاء الطلب =====
    new_order = Order(
        quantity=qty,
        total_price=total_price,
        delivery_fee=delivery_fee,
        delivery_type=delivery_type,
        address=address if address else None,
        invoice_number=invoice_number,
        user_id=user.id,
        drug_id=drug.id,
        pharmacist_id=drug.pharmacist_id,
        status="قيد الانتظار"
    )

    db.session.add(new_order)
    db.session.commit()

    # ===== إنشاء الفاتورة =====
    from generate_invoice import generate_invoice
    generate_invoice(new_order)

   


    # إذا الدفع إلكتروني، حول المستخدم لصفحة الدفع
    if payment_method == "online":
        flash("✅ سيتم توجيهك لبوابة الدفع الإلكتروني", "info")
        return redirect(url_for("online_payment", order_id=new_order.id))

    flash("✅ تم تأكيد الطلب بنجاح")
    return redirect(url_for("track_order"))







# ================= تحديث حالة الطلب =================
@app.route("/update_order_status", methods=["POST"])
def update_order_status():
    if "pharmacist_id" not in session and not session.get("admin"):
        return redirect(url_for("login"))

    order_id = request.form.get("order_id")
    status = request.form.get("status")

    order = Order.query.get(order_id)

    if order and status:
        order.status = status
        order.seen = False
        db.session.commit()
        flash("تم تحديث الحالة")

    return redirect(request.referrer or url_for("pharmacist_orders"))



# ================= TRACK ORDER =================
@app.route("/track_order", methods=["GET", "POST"])
def track_order():

    orders = []
    query = None

    if request.method == "POST":
        query = request.form.get("query", "").strip()

        if not query:
            flash("أدخل رقم الهاتف أو رقم الطلب", "warning")
            return render_template("track_order.html", orders=[], query=query)

        # 🔹 البحث برقم الهاتف
        user = User.query.filter_by(phone=query).first()

        if user:
            orders = Order.query.filter_by(user_id=user.id)\
                .order_by(Order.created_at.desc()).all()

        # 🔹 البحث برقم الفاتورة
        elif query.isdigit():
            orders = Order.query.filter_by(
                invoice_number=int(query)
            ).all()

        else:
            flash("لا يوجد مستخدم بهذا الرقم", "warning")

        if request.method == "POST" and not orders:
            flash("لم يتم العثور على طلبات", "warning")

    return render_template("track_order.html", orders=orders, query=query)





# ================= ADMIN LOGIN =================

@app.route("/admin_login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        if request.form.get("username") == "admin" and \
           request.form.get("password") == "11111111":

            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash("خطأ في الدخول")

    return render_template("admin_login.html")


@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    all_pharmacists = Pharmacist.query.all()
    all_drugs = Drug.query.all()
    all_orders = Order.query.all()

    return render_template(
        "admin_dashboard.html",
        pharmacists=all_pharmacists,
        drugs=all_drugs,
        orders=all_orders
    )
    


# =================  =================




@app.route("/register_user", methods=["GET","POST"])
def register_user():
    if request.method == "POST":
        name = request.form.get("name").strip()
        phone = request.form.get("phone").strip()
        password = request.form.get("password")
        password2 = request.form.get("password2")

        if not all([name, phone, password, password2]):
            flash("❌ أكمل جميع البيانات", "danger")
            return redirect(url_for("register_user"))

        if password != password2:
            flash("❌ كلمتا المرور غير متطابقتين", "danger")
            return redirect(url_for("register_user"))

        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            flash("❌ رقم الهاتف مستخدم مسبقًا", "danger")
            return redirect(url_for("register_user"))

        new_user = User(
            name=name,
            phone=phone,
            password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        flash("✅ تم إنشاء الحساب بنجاح، يمكنك تسجيل الدخول الآن", "success")
        return redirect(url_for("login_user"))

    return render_template("register_user.html")

# ================= تسجيل الدخول =================
@app.route("/login_user", methods=["GET","POST"])
def login_user():
    if request.method == "POST":
        phone = request.form.get("phone").strip()
        password = request.form.get("password")

        if not phone or not password:
            flash("أكمل جميع البيانات", "warning")
            return redirect(url_for("login_user"))

        user = User.query.filter_by(phone=phone).first()
        if not user or not check_password_hash(user.password, password):
            flash("❌ رقم الهاتف أو كلمة المرور غير صحيحة", "danger")
            return redirect(url_for("login_user"))

        session["user_id"] = user.id
        session["user_name"] = user.name
        session["user_phone"] = user.phone

        flash(f"✅ أهلاً {user.name}", "success")
        return redirect(url_for("index"))

    return render_template("login_user.html")

# ================= تسجيل الخروج =================
@app.route("/user_logout")
def user_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_phone", None)
    flash("✅ تم تسجيل الخروج", "success")
    return redirect(url_for("index"))



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin_logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# ===== تشغيل التطبيق محليًا فقط =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
