from . import models
from google.appengine.ext import ndb
import appengine_config
import datetime
import os
import webapp2

DOWNLOAD_URL_FORMAT = 'https://www.googleapis.com/drive/v3/files/{resource_id}?alt=media&key={key}'

THUMBNAIL_URL_FORMAT = 'https://drive.google.com/thumbnail?sz=w{size}&id={resource_id}'

CONFIG = appengine_config.CONFIG


class Asset(models.Model):
  size = ndb.IntegerProperty()
  build = ndb.IntegerProperty()
  mimetype = ndb.StringProperty()
  md5 = ndb.StringProperty()
  parents = ndb.KeyProperty(repeated=True)
  basename = ndb.StringProperty()
  ext = ndb.StringProperty()
  url = ndb.StringProperty()
  icon_url = ndb.StringProperty()
  num_downloads = ndb.IntegerProperty(default=0)

  @classmethod
  def process(cls, resp):
    resource_id = resp['id']
    ent = cls.get_or_instantiate(resource_id)
    ent.resource_id = resource_id
    ent.mimetype = resp['mimeType']
    ent.size = int(resp['fileSize'])
    ent.url = resp['webContentLink']
    ent.icon_url = resp['iconLink']
    ent.parse_title(resp['title'])
    ent.md5 = resp['md5Checksum']
    ent.modified = cls.parse_datetime_string(resp['modifiedDate'])
    ent.synced = datetime.datetime.now()
    ent.parents = cls.generate_parent_keys(resp['parents'])
    ent.basename, ent.ext = os.path.splitext(resp['title'])
    ent.put()

  @property
  def media_url(self):
    return DOWNLOAD_URL_FORMAT.format(
        resource_id=self.resource_id,
        key=CONFIG['apikey'])

  @property
  def thumbnail_url(self):
    return THUMBNAIL_URL_FORMAT.format(
        resource_id=self.resource_id,
        size=250)

  @property
  def download_url(self):
    return '/assets/{}'.format(self.resource_id)

  @classmethod
  def search_by_downloads(cls):
    query = cls.query()
    query = query.filter(cls.num_downloads != 0)
    query = query.order(-cls.num_downloads)
    return query.fetch()

  @webapp2.cached_property
  def parent(self):
    return self.parents[0].get()
