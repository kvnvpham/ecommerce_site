from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, EmailField, PasswordField, IntegerField, FloatField, SubmitField
from wtforms.validators import InputRequired, Email, Length, NumberRange
from flask_ckeditor import CKEditorField


class RegisterForm(FlaskForm):
    name = StringField(label="Name", validators=[InputRequired()])
    email = EmailField(label="Email", validators=[InputRequired(), Email()])
    password = PasswordField(label="Password", validators=[InputRequired(), Length(min=8)])
    submit = SubmitField(label="Register")


class LoginForm(FlaskForm):
    email = EmailField(label="Email", validators=[InputRequired(), Email()])
    password = PasswordField(label="Password", validators=[InputRequired()])
    submit = SubmitField(label="Login")


class AddProductForm(FlaskForm):
    name = StringField(label="Product Name", validators=[InputRequired()])
    type = IntegerField(label="Product Type ID", validators=[InputRequired()])
    price = FloatField(label="Price", validators=[InputRequired()])
    description = CKEditorField(label="Description", validators=[InputRequired()])
    image = FileField(label="Image", validators=[FileRequired(), FileAllowed(['jpg', 'png'], "Images Only")])
    submit = SubmitField(label="Submit")


class AddToCartForm(FlaskForm):
    quantity = IntegerField(label="Quantity",
                            validators=[InputRequired(), NumberRange(min=1)],
                            default=1,
                            render_kw={"min": "1"})
    add = SubmitField(label="Add to cart")
