# !/usr/bin/env python
from sqlalchemy.orm import sessionmaker
from flask import jsonify
from flask import Flask, render_template, url_for, request, redirect, flash,\
                jsonify
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from flask import session as login_session
import random
import string
from sqlalchemy import and_, or_
from database_setup import Base, Category, Items, User
from app_forms import NewCategoryForm, NewItemForm, EditCategoryForm,\
                    EditItemForm
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from flask_uploads import UploadSet, IMAGES, configure_uploads,\
                    patch_request_class
from werkzeug import secure_filename
import os
from functools import wraps


app = Flask(__name__)

# Fetch the Client ID from the Google Sign based JSON file
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "CATALOGUE APPLICATION"

# Configure file upload using flask_uploads
images = UploadSet('images', IMAGES)
app.config['UPLOADED_IMAGES_DEST'] = 'static/img'
configure_uploads(app, images)


# Application database
engine = create_engine('sqlite:///catalogue.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Login page generate and use unique tokens to authenticate user using
# 3rd party login Example: Google Sign in


@app.route('/login')
def showlogin():
    '''
    Renders a login page with a unique token

    Arguments: None
    '''
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

# Authenticate users using Google Sign feature


@app.route('/gconnect', methods=['POST'])
def gconnect():
    '''
    Authenticates user using Google Sign feature

    Arguments: None
    '''
    # Validate the state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # check  that access token is valid

    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # if there was an error in access_token info, abort
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that access_token is used for intended user
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user_id doesn't match given user ID"), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that access_token is valid for this app
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's "), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('glus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # store the access_token in the session for later use
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # Add provider to login session
    login_session['provider'] = 'google'

    # see if user exists, if not make one
    user_id = getUserID(data['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h2 class="loginWelcomeText">Welcome, '
    output += login_session['username']
    output += '!</h2>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 250px; height: 250px;'
    output += 'border-radius: 150px;'
    output += '-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("You are now logged in as %s" % login_session['username'])
    return output

# Creates a user against a login_session usig the login_session details
# name of the user, email of the user and picture URL of the user


def createUser(login_session):
    '''
    Creates a User against a login_session. Registers a user into database.

    Arguments:
    login_session: session of an active User
    '''
    newUser = User(
        name=login_session['username'],
        email=login_session['email'],
        picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

# Get the User information from the database


def getUserInfo(user_id):
    '''
    Fetches User information from database

    Arguments:

    user_id: ID of user
    '''
    user = session.query(User).filter_by(id=user_id).one()
    return user

# Get User ID against a user's email from the application database


def getUserID(email):
    '''
    Fetches user id from the database.abs

    Arguments:

    email: email address of a user
    '''
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    '''
    Disconnects a connected user

    Arguments: None
    '''
    # Only disconnect a connected user
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == "200":
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        response = make_response(json.dumps('Sucessfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('showcontents'))
    else:
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        response = make_response(
            json.dumps('Failed to revoke token for given user '), 400)
        response.headers['Content-Type'] = 'application/json'
        return response

def login_required(f):
    '''It verifies if its an authenticated user'''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' in login_session:
            return f(*args, **kwargs)
        else:
            return redirect('/login')
    return decorated_function

# Fetches JSON for complete Catalogue.

@app.route('/catalogue.JSON')
@login_required
def showenteriesJSON():
    ''' creating the returning json object
        for getting all categories and respective items
    '''
    allcategories = session.query(Category).all()
    categories = []
    for cat in allcategories:
        tempIde = {
                'id': cat.id,
                'name': cat.name
            }
        items = session.query(Items).filter_by(category_id=cat.id).all()
        if len(items) is not 0:
            items_list = [item.serialize for item in items]
            tempIde['items'] = items_list
        categories.append(tempIde)
    return jsonify({'Category': categories})

# Get JSON for all items in a category


@app.route('/catalogue/<category_name>/categoryitems.JSON')
@login_required
def getitemsJSON(category_name):
    '''
    Get JSON for all items in a category available in the application database

    Arguments:
    category_name: Name of the category
    '''
    aCategory = session.query(Category).filter_by(name=category_name).one()
    allitems = session.query(Items).filter_by(category_id=aCategory.id).all()
    return jsonify(Items=[item.serialize for item in allitems])

# Get JSON for all categories


@app.route('/catalogue/categories.JSON')
@login_required
def getAllCategoriesJSON():
    '''
    Get JSON for all categories available in application database.

    Arguments: None
    '''
    allCategories = session.query(Category).all()
    return jsonify(
        Categories=[category.serialize for category in allCategories])

# Get JSON for a item in a category


@app.route('/catalogue/<category_name>/<item_name>/JSON')
@login_required
def getAItemJSON(category_name, item_name):
    '''
    Get JSON for a item present in a category in the application database

    Arguments:
    category_name: Name of the Category
    item_name: Name of the item
    '''
    aCategory = session.query(Category).filter_by(name=category_name).one()
    aItem = session.query(Items).filter(and_(
        Items.category_id == aCategory.id, Items.title == item_name)).one()
    return jsonify(Item=aItem.serialize)

# Creates a new Category (CRUD: CREATE)


@app.route('/catalogue/category/new', methods=['GET', 'POST'])
@login_required
def newcategory():
    '''
    Creates a new Category for an authenticated/registered user

    Arguments: None
    '''
    form = NewCategoryForm(request.form)   # form validation

    if request.method == 'POST' and form.validate_on_submit():
        newCategory = Category(
            name=form.name.data, user_id=login_session['user_id'])
        session.add(newCategory)
        session.commit()
        flash("New Category added!")
        return redirect(url_for('showcontents'))
    else:
        allcategories = session.query(Category).all()
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'newcategory.html',
            allcategories=allcategories,
            creator=creator,
            form=form)

# Edit a Category (CRUD: UPDATE)


@app.route('/catalogue/<category_name>/edit', methods=['GET', 'POST'])
@login_required
def editcategory(category_name):
    '''
    Edit a Category

    Arguments:
    category_name: Name of the category
    '''
    editcategory = session.query(Category).filter_by(name=category_name).one()

    form = EditCategoryForm(request.form)   # validation form

    if editcategory.user_id != login_session['user_id']:
        alertJS = "<script>function myFunction() "
        alertJS += "{alert('You are not authorized to edit this."
        alertJS += " Please create your own in order to edit.'"
        alertJS += ");}</script><body onload='myFunction()''>"
        return alertJS
    if request.method == 'POST' and form.validate_on_submit():
        if form.name.data:
            editcategory.name = form.name.data
        editcategory.user_id = login_session['user_id']
        session.add(editcategory)
        session.commit()
        flash("Category edited!")
        return redirect(
            url_for('showallitems', category_name=editcategory.name))
    else:
        allcategories = session.query(Category).all()
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'editcategories.html', category_name=editcategory.name,
            editcategory=editcategory, creator=creator, form=form)

# Delete a Category (CRUD: DELETE)


@app.route('/catalogue/<category_name>/delete', methods=['GET', 'POST'])
@login_required
def deletecategory(category_name):
    '''
    Delete a Category

    Arguments:
    category_name: Name of the category
    '''
    categorytodelete = session.query(Category).filter_by(
        name=category_name).one()

    # Fetch all the items in a category
    # created by different users.
    items_all = session.query(Items).filter_by(
        category_id=categorytodelete.id).all()
    # check and alert if any item present in this
    # category which is not created by current
    # user and delete the rest

    if request.method == 'POST':
        if categorytodelete.user_id != login_session['user_id']:
            alertJS = "<script>function myFunction() "
            alertJS += "{alert('You are not authorized to delete this."
            alertJS += " Please create your own in order to delete.'"
            alertJS += ");}</script><body onload='myFunction()''>"
            return alertJS
        for item in items_all:
            if item.user_id != login_session['user_id']:
                alertJS = "<script>function myFunction() "
                alertJS += "{alert('You are not authorized to delete this."
                alertJS += " This category has items of other users.'"
                alertJS += ");}</script><body onload='myFunction()''>"
                return alertJS
        for item in items_all:
            old_filename = item.image_filename
            old_file_path = images.path(old_filename)
            os.remove(old_file_path)
            session.delete(item)
            session.commit()
        session.delete(categorytodelete)
        session.commit()
        flash("Category deleted!")
        return redirect(url_for('showcontents'))
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'deletecategory.html', category_name=category_name,
            categorytodelete=categorytodelete, creator=creator)

# Fetches categories and latest items (CRUD: READ)


@app.route('/', methods=['GET'])
def showcontents():
    '''
    Fetches contents from the catalogue from the application database

    Arguments: None

    '''
    categories = session.query(Category).all()
    numberofrecords = len(categories)
    items = session.query(Items).order_by(
        Items.title.asc()).all()
    if 'username' not in login_session:
        return render_template(
            'index.html', categories=categories, items=items)
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'pindex.html', categories=categories, items=items, creator=creator)

# Fetches items in a category (CRUD: READ)


@app.route('/catalogue/<category_name>/items', methods=['GET'])
def showallitems(category_name):
    '''
    Fetches all items in a category from the application database

    Arguments:
    cateegory_name: Name of the category
    '''
    categories = session.query(Category).all()
    category = session.query(Category).filter_by(name=category_name).first()
    items = session.query(Items).filter_by(category_id=category.id).all()
    numberofrecords = len(items)
    if 'username' not in login_session:
        return render_template(
            'items.html', category_name=category_name,
            categories=categories, items=items,
            numberofrecords=numberofrecords)
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'pitems.html', category_name=category_name,
            categories=categories, items=items,
            numberofrecords=numberofrecords,
            creator=creator)

# Fetches an item in Category (CRUD: READ)


@app.route('/catalogue/<category_name>/<item_name>', methods=['GET'])
def showaitem(category_name, item_name):
    '''
    Fetches an item in a category from the application database

    Arguments:
    category_name: Name of the Category
    item_name: Name of the item
    '''
    category = session.query(Category).filter_by(name=category_name).first()
    category_items = session.query(Items).filter(and_(
        Items.category_id == category.id,
        Items.title == item_name)).one()
    if 'username' not in login_session:
        return render_template(
            'itemdescription.html', category_name=category_name,
            category_items=category_items)
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'pitemdescription.html', category_name=category_name,
            category_items=category_items, creator=creator)


# Creates a new item (CRUD: CREATE)


@app.route('/catalogue/new', methods=['GET', 'POST'])
@login_required
def newitem():
    '''
    Creates a new item

    Arguments: None
    '''

    form = NewItemForm()   # form validation

    if request.method == 'POST' and form.validate_on_submit():
        cats = session.query(Category).filter_by(
            name=request.form['category_name']).first()

        filename = images.save(request.files['image'])
        url = images.url(filename)

        newItem = Items(
            title=form.title.data,
            description=form.description.data,
            image_filename=filename,
            image_url=url,
            category_id=cats.id,
            user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        flash("New item added!")
        return redirect(url_for('showallitems',
                        category_name=request.form['category_name']))
    else:
        allcategories = session.query(Category).all()
        creator = getUserInfo(login_session['user_id'])
        return render_template(
                'newitem.html',
                allcategories=allcategories,
                creator=creator,
                form=form)


# Edit an item (CRUD: UPDATE)


@app.route(
    '/catalogue/<category_name>/<item_name>/edit', methods=['GET', 'POST'])
@login_required
def edititem(category_name, item_name):
    '''
    Edit an item in a category

    Arguments:
    category_name: Name of the Category
    item_name: Name of the item
    '''
    category = session.query(Category).filter_by(name=category_name).first()
    editedItem = session.query(Items).filter(and_(
        Items.category_id == category.id, Items.title == item_name)).one()

    if login_session['user_id'] != editedItem.user_id:
        alertJS = "<script>function myFunction() "
        alertJS += "{alert('You are not authorized to edit this."
        alertJS += " Please create your own in order to edit.'"
        alertJS += ");}</script><body onload='myFunction()''>"
        return alertJS

    form = EditItemForm()   # validation form

    if request.method == 'POST' and form.validate_on_submit():
        if form.title.data:
            editedItem.title = form.title.data
        if form.description.data:
            editedItem.description = form.description.data
        if request.files['image']:
            old_filename = editedItem.image_filename
            old_file_path = images.path(old_filename)
            os.remove(old_file_path)
            filename = images.save(request.files['image'])
            url = images.url(filename)
            editedItem.image_filename = filename
            editedItem.image_url = url
        if request.form['category_name']:
            fetcheCategory = session.query(Category).filter_by(
                name=request.form['category_name']).first()
            editedItem.category_id = fetcheCategory.id
            editedItem.user_id = login_session['user_id']
        session.add(editedItem)
        session.commit()
        flash("Item edited!")
        return redirect(url_for(
            'showallitems', category_name=request.form['category_name']))
    else:
        allcategories = session.query(Category).all()
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'edititems.html',
            category_name=category_name,
            item_name=item_name,
            item=editedItem,
            allcategories=allcategories,
            creator=creator, form=form)


# Deletes an item (CRUD: DELETE)


@app.route(
    '/catalogue/<category_name>/<item_name>/delete', methods=['GET', 'POST'])
@login_required
def deleteitem(category_name, item_name):
    '''
    Deletes an item in a category

    Arguments:
    category_name: Name of the category
    item_name: Name of the item
    '''

    category = session.query(Category).filter_by(name=category_name).first()
    itemtodelete = session.query(Items).filter(and_(
        Items.category_id == category.id, Items.title == item_name)).one()
    if login_session['user_id'] != itemtodelete.user_id:
        alertJS = "<script>function myFunction() "
        alertJS += "{alert('You are not authorized to delete this."
        alertJS += " Please create your own in order to delete.'"
        alertJS += ");}</script><body onload='myFunction()''>"
        return alertJS
    if request.method == 'POST':
        filename = itemtodelete.image_filename
        file_path = images.path(filename)
        os.remove(file_path)
        session.delete(itemtodelete)
        session.commit()
        flash("Item deleted!")
        return redirect(url_for('showallitems', category_name=category_name))
    else:
        creator = getUserInfo(login_session['user_id'])
        return render_template(
            'deleteitem.html',
            category_name=category_name,
            item_name=item_name,
            item=itemtodelete,
            creator=creator)


if __name__ == '__main__':
    app.debug = True
    app.config['JSON_SORT_KEYS'] = False
    app.secret_key = "SUPER SECRET KEY!"
    app.run(host='0.0.0.0', port=8000)
