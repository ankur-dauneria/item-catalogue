# !/usr/bin/env python
# Creation of database with object relational model (ORM)
# using sqlalchemy

import os
import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

# Class User to store the id, name, email, picture
# in the table 'user'


class User(Base):
    '''
    Class user stores details of the user
    in table (user)
    '''
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))

# Class Category to store category related details
# like id, name, user id in table 'category'


class Category(Base):
    '''
    Class category stores details of the category
    in table (category)
    '''
    __tablename__ = 'category'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        '''
        Returns a serialized object in key, value pair
        for JSON endpoints
        '''
        return {
            'id': self.id,
            'name': self.name
        }

# Class Items to store the item details like
# id, title, description, category id, user id
# in table 'items'


class Items(Base):
    '''
    Class Items stores item related details in
    table 'items'
    '''
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    description = Column(String(750))
    image_filename = Column(String(250), default=None, nullable=True)
    image_url = Column(String(250), default=None, nullable=True)
    category_id = Column(Integer, ForeignKey('category.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    category = relationship(Category)

    @property
    def serialize(self):
        '''
        Returns a serialized object in key, value pair
        for JSON endpoints
        '''
        return {
            'cat_id': self.category_id,
            'id': self.id,
            'title': self.title,
            'description': self.description
        }

engine = create_engine('sqlite:///catalogue.db')

Base.metadata.create_all(engine)
