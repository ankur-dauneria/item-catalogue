# This file contains various classes for form validator
# used while creation and editing of categories and
# items

# import modules
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Required, Length
from flask_wtf.file import FileField, FileAllowed, FileRequired

# New category form validator class


class NewCategoryForm(FlaskForm):
    '''
    This Class validates new category form.
    '''
    name = StringField(
        'Category name', validators=[Required(), Length(1, 250)])

# New Item form validator class


class NewItemForm(FlaskForm):
    '''
    This Class validates new Item form.
    '''
    title = StringField('Item name', validators=[Required(), Length(1, 250)])
    description = StringField(
        'Item description', validators=[Required(), Length(1, 750)])
    image = FileField(
        'Item Image', validators=[FileRequired(), FileAllowed(
            ['jpg', 'png'], 'Images only!')])

# Edit category form validator class


class EditCategoryForm(FlaskForm):
    '''
    This Class validates edit Category form.
    '''
    name = StringField(
        'Category name', validators=[Required(), Length(1, 250)])

# Edit item form validator class


class EditItemForm(FlaskForm):
    '''
    This Class validates edit Item form
    '''
    title = StringField(
        'Item name', validators=[Required(), Length(1, 250)])
    description = StringField(
        'Item description', validators=[Required(), Length(1, 750)])
    image = FileField('Item Image', validators=[FileRequired(), FileAllowed(
        ['jpg', 'png'], 'Images only!')])
