from . import messages
from . import models
from google.appengine.ext import ndb
import appengine_config


class Admin(models.Model):
  email = ndb.StringProperty()
  created = ndb.DateTimeProperty(auto_now_add=True)
  created_by_key = ndb.KeyProperty()
  receives_email = ndb.BooleanProperty(default=True)

  @classmethod
  def is_admin(cls, email):
    if email in appengine_config.CONFIG['admins']:
      return True
    return cls.get_by_email(email)

  @classmethod
  def list_emails(cls):
    emails = []
    for admin in cls.list():
      emails.append(admin.email)
    return emails

  @classmethod
  def create(cls, email, created_by):
    existing = cls.get_by_email(email)
    if existing:
      return existing
    ent = cls(id=email)
    ent.email = email
    ent.created_by_key = created_by.key
    ent.put()
    return ent

  @classmethod
  def list(cls):
    query = cls.query()
    query = query.order(-cls.created)
    return query.fetch()

  @classmethod
  def get_by_email(cls, email):
    return cls.get_by_id(email)

  def to_message(self):
    message = messages.AdminMessage()
    message.email = self.email
    message.created = self.created
    message.created_by = self.created_by.to_message()
    message.receives_email = self.receives_email
    message.ident = self.ident
    return message
