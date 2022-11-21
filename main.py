from flask import Flask, render_template, redirect, url_for, request, flash, abort, session
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from forms import RegisterForm, LoginForm, AddProductForm, AddToCartForm
from flask_ckeditor import CKEditor
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
import stripe
from datetime import date
import os

UPLOAD_FOLDER = "static/images/products"
STRIPE_PUBLISH_KEY = os.environ.get("STRIPE_PUB_KEY")
stripe.api_key = os.environ.get("STRIPE_KEY")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

Bootstrap(app)
ckeditor = CKEditor(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///online_store.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)

    product = relationship("Product", back_populates="customer")
    cart = relationship("CartItems", back_populates="customer_cart")


class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    image = db.Column(db.String, nullable=False)
    type = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)

    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    customer = relationship("User", back_populates="product")
    cart_qty = relationship("CartItems", back_populates="product")


class CartItems(db.Model):
    __tablename__ = "cart"
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)

    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    customer_cart = relationship("User", back_populates="cart")
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product = relationship("Product", back_populates="cart_qty")


with app.app_context():
    db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id == 1:
            return f(*args, **kwargs)
        else:
            abort(403)
    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    flash("Please Login Or Register.")
    return redirect(url_for("login"))


@app.route("/")
def home():
    if current_user.is_authenticated:
        return render_template("index.html", user_id=current_user.id)

    return render_template("index.html", user_id=0)


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("That Email Already Exists, Please Login.")
            return redirect(url_for("login"))

        secure_pw = generate_password_hash(
            password=form.password.data,
            method='pbkdf2:sha256',
            salt_length=10
        )

        new_user = User(
            name=form.name.data,
            email=form.email.data,
            password=secure_pw,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        if session.get("cart"):
            cart = session.get("cart")
            for key, value in cart.items():
                product = Product.query.get(key)
                cart_items = CartItems(
                    quantity=value,
                    product=product,
                    customer_cart=new_user
                )
                db.session.add(cart_items)
            db.session.commit()

        return redirect(url_for("home", user_id=current_user.id))

    return render_template("register.html", form=form, user_id=0)


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user)

                if session.get("cart"):
                    cart = session.get("cart")
                    for key, value in cart.items():
                        product = Product.query.get(key)
                        cart_items = CartItems(
                            quantity=value,
                            product=product,
                            customer_cart=user
                        )
                        db.session.add(cart_items)
                    db.session.commit()

                return redirect(url_for("home", user_id=current_user.id))
            else:
                flash("Invalid Password, Please Enter The Correct Password")
                return redirect(url_for("login"))
        else:
            flash("Invalid Email, Please Enter the Correct Email or Register")
            return redirect(url_for("login"))

    return render_template("login.html", form=form, user_id=0)


@app.route("/logout")
@login_required
def logout():
    session.pop("cart", None)
    logout_user()
    return redirect(url_for('home'))


@app.route("/add-product", methods=['GET', 'POST'])
@login_required
@admin_only
def add_product():
    form = AddProductForm()

    if form.validate_on_submit():
        file = form.image.data
        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        user = User.query.get(current_user.id)
        new_product = Product(
            name=form.name.data,
            image=f"images/products/{filename}",
            type=form.type.data,
            description=form.description.data,
            price=form.price.data,
            customer=user
        )
        db.session.add(new_product)
        db.session.commit()

        format_price = str(form.price.data).replace(".", "")
        stripe.Product.create(id=str(new_product.id),
                              name=form.name.data)
        stripe.Price.create(product=str(new_product.id),
                            unit_amount=int(format_price),
                            currency="usd")

        return redirect(url_for("home", user_id=current_user.id))

    return render_template("add_product.html", form=form, user_id=current_user.id)


@app.route("/delete-product/<int:item_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def delete_product(item_id):
    product = Product.query.get(item_id)

    stripe.Product.create(active=False, name=product.name)

    db.session.delete(product)
    db.session.commit()

    return redirect(url_for("home", user_id=current_user.id))


@app.route("/product/<int:type_id>")
def show_products(type_id):
    all_products = Product.query.filter_by(type=type_id)
    if current_user.is_authenticated:
        return render_template("all_products.html", products=all_products, type_id=type_id, user_id=current_user.id)

    return render_template("all_products.html", products=all_products, type_id=type_id, user_id=0)


@app.route("/get-product/<int:user_id>/<int:item_id>", methods=['GET', 'POST'])
def get_product(user_id, item_id):
    product = Product.query.get(item_id)
    form = AddToCartForm()

    if form.validate_on_submit():
        if current_user.is_authenticated and user_id == current_user.id:
            user = User.query.get(current_user.id)
            cart = CartItems(
                quantity=form.quantity.data,
                product=product,
                customer_cart=user
            )
            db.session.add(cart)
            db.session.commit()
            return redirect(url_for("show_products", type_id=product.type, user_id=user_id))
        elif user_id == 0:
            if session.get("cart"):
                cart = session.get("cart")
                cart[str(product.id)] = form.quantity.data
                session["cart"] = cart
            else:
                cart = {str(product.id): form.quantity.data}
                session["cart"] = cart

            return redirect(url_for("show_products", type_id=product.type, user_id=user_id))
        else:
            abort(403)

    return render_template("product.html", product=product, form=form, user_id=user_id)


@app.route("/cart/<int:user_id>")
def show_cart(user_id):
    if current_user.is_authenticated and user_id == current_user.id:
        user = User.query.get(user_id)

        total = 0
        for item in user.cart:
            total += item.product.price * item.quantity

        return render_template("cart.html", user=user, item_total=round(total, 2), user_id=current_user.id)
    elif user_id == 0:
        total = 0
        if session.get("cart"):
            cart = session.get("cart")
            session_cart = []
            for key, value in cart.items():
                product = Product.query.get(key)
                session_cart.append(
                    {
                        "id": key,
                        "image": product.image,
                        "name": product.name,
                        "qty": value,
                        "price": product.price
                     }
                )
                total += product.price * value

            return render_template("cart.html", session=session_cart, item_total=round(total, 2), user_id=0)

        return render_template("cart.html", session=None, item_total=round(total, 2), user_id=0)
    else:
        abort(403)


@app.route("/update/<int:user_id>/<int:cart_id>", methods=['GET', 'POST'])
def update_item(user_id, cart_id):
    item = request.args.get("item_id")
    update_product = Product.query.get(item)

    if current_user.is_authenticated and user_id == current_user.id:
        update_cart = CartItems.query.get(cart_id)
        form = AddToCartForm(quantity=update_cart.quantity)

        if form.validate_on_submit():
            if current_user.is_authenticated and user_id == current_user.id:
                update_cart.quantity = form.quantity.data
                db.session.commit()
                return redirect(url_for("show_cart", user_id=user_id))
            else:
                abort(403)

        return render_template(
            "product.html",
            form=form,
            product=update_product,
            user_id=user_id,
            cart_id=cart_id,
            is_update=True
        )
    elif user_id == 0:
        form = AddToCartForm(quantity=cart_id)  # cart_id is session qty

        if form.validate_on_submit():
            cart = session.get("cart")
            if str(update_product.id) in cart:
                cart[str(update_product.id)] = form.quantity.data
                session["cart"] = cart

            return redirect(url_for("show_cart", user_id=user_id))

        return render_template(
            "product.html",
            form=form,
            product=update_product,
            user_id=user_id,
            cart_id=cart_id,
            is_update=True
        )
    else:
        abort(403)


@app.route("/remove/<int:user_id>/<cart_id>")
def remove_item(user_id, cart_id):
    if current_user.is_authenticated and user_id == current_user.id:
        cart_item = CartItems.query.get(cart_id)
        db.session.delete(cart_item)
        db.session.commit()
        return redirect(url_for("show_cart", user_id=user_id))
    elif user_id == 0:
        item = request.args.get("item_id")
        cart = session.get("cart")
        if item in cart:
            cart.pop(item)
            session["cart"] = cart
        return redirect(url_for("show_cart", user_id=user_id))
    else:
        abort(403)


@app.route("/checkout/<int:user_id>")
@login_required
def checkout(user_id):
    if user_id == current_user.id:
        try:
            user = User.query.get(user_id)

            cart = []
            for item in user.cart:
                response = stripe.Price.search(query=f"product:'{item.product.id}'")
                price_id = response["data"][0]["id"]

                cart.append(
                    {
                        "price": price_id,
                        "quantity": item.quantity
                    }
                )

            checkout_session = stripe.checkout.Session.create(
                shipping_address_collection={"allowed_countries": ["US", "CA"]},
                shipping_options=[
                    {
                        "shipping_rate_data": {
                            "type": "fixed_amount",
                            "fixed_amount": {"amount": 499, "currency": "usd"},
                            "display_name": "Standard Shipping",
                            "delivery_estimate": {
                                "minimum": {"unit": "business_day", "value": 5},
                                "maximum": {"unit": "business_day", "value": 7}
                            }
                        }
                    }
                ],
                line_items=cart,
                mode="payment",
                success_url=url_for("success", user_id=user_id, _external=True),
                cancel_url=url_for("cancel", user_id=user_id, _external=True)
            )

        except Exception as e:
            return str(e)

        return redirect(checkout_session.url, code=303)


@app.route("/success/<int:user_id>")
def success(user_id):
    if user_id == current_user.id:
        user = User.query.get(user_id)

        for item in user.cart:
            db.session.delete(item)
        db.session.commit()

    return render_template("success.html", user_id=user_id)


@app.route("/cancel/<int:user_id>")
def cancel(user_id):
    return render_template("cancel.html", user_id=user_id)


@app.context_processor
def inj_copyright():
    return {"year": date.today().year}


if __name__ == "__main__":
    app.run()

