from . import messages
from . import models
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from google.appengine.ext import blobstore
import appengine_config
import datetime
import os
import re
import webapp2

DOWNLOAD_URL_FORMAT = 'https://www.googleapis.com/drive/v3/files/{resource_id}?alt=media&key={key}'

THUMBNAIL_URL_FORMAT = 'https://drive.google.com/thumbnail?sz=w{size}&id={resource_id}'

CONFIG = appengine_config.CONFIG

FILENAME_IDENTIFIERS_TO_LOCALES = {
    '_AR_': 'ar',
    '_FR-CA_': 'fr-ca',
    '_DE_': 'de',
    '_ZH-CN_': 'zh-cn',
    '_ZH-TW_': 'zh-tw',
    '_NL_': 'nl',
    '_EN-GB_': 'en-gb',
    '_FR_': 'fr',
    '_DE_': 'de',
    '_IT_': 'it',
    '_JA_': 'ja',
    '_KO_': 'ko',
    '_PL_': 'pl',
    '_PT_': 'pt',
    '_RU_': 'ru',
    '_ES_': 'es',
    '_TH_': 'th',
    '_TR_': 'tr',
}


class Asset(models.BaseResourceModel):
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
  gcs_path = ndb.StringProperty()
  gcs_thumbnail_path = ndb.StringProperty()
  etag = ndb.StringProperty()
  metadata = msgprop.MessageProperty(
      messages.AssetMetadata, indexed_fields=['width', 'height', 'label'])

  @classmethod
  def process(cls, resp, gcs_path=None, gcs_thumbnail_path=None):
    resource_id = resp['id']
    ent = cls.get_or_instantiate(resource_id)
    ent.resource_id = resource_id
    ent.mimetype = resp['mimeType']
    ent.size = int(resp['fileSize'])
    ent.url = resp['webContentLink']
    ent.icon_url = resp['iconLink']
    ent.parse_title(resp['title'])
    ent.md5 = resp['md5Checksum']
    ent.etag = resp['etag']
    ent.gcs_path = gcs_path
    ent.gcs_thumbnail_path = gcs_thumbnail_path
    ent.modified = cls.parse_datetime_string(resp['modifiedDate'])
    ent.synced = datetime.datetime.now()
    ent.parents = cls.generate_parent_keys(resp['parents'])
    ent.basename, ent.ext = os.path.splitext(resp['title'])
    ent.set_metadata(resp)
    ent.put()

  @classmethod
  def get_group(cls, parent_key=None):
    query = cls.query()
    query = query.filter(cls.parents == parent_key)
    ents = query.fetch()
    asset_messages = [ent.to_message() for ent in ents]
    folder_message = parent_key.get().to_message()
    return folder_message, asset_messages

  def set_metadata(self, resp):
    metadata = messages.AssetMetadata()
    title = resp['title']  # Formatted: CB_US_STD_ATTRACT_HANGING_LANDSCAPE_48x24.ext
    base, ext = os.path.splitext(resp['title'])
    metadata.base = base
    metadata.ext = ext

    # Language.
    for key, value in FILENAME_IDENTIFIERS_TO_LOCALES.iteritems():
        if key in base:
            metadata.language = value
            break

    # Width and height.
    for part in base.split('_'):
      part = re.sub('[p][x]', '', part)
      match = re.match('(\d*)x(\d*)', part)
      if match:
        width, height = match.groups()
        metadata.width = int(width)
        metadata.height = int(height)
        metadata.dimensions = '{}x{}'.format(width, height)

    # Label.
    if '_STD_' in base:
      metadata.label = 'Standard'
    elif '_PROMO_' in base:
      metadata.label = 'Promotional'
    elif '_CO-BRAND_' in base:
      metadata.label = 'Co-branding'
    elif '_CTA_' in base:
      metadata.label = 'Call-to-action'
    elif '_CIRCULAR_' in base:
      metadata.label = 'Circular'
    elif '_SOCIALMEDIA_' in base:
      metadata.label = 'Social media'

    self.metadata = metadata

  @property
  def media_url(self):
    return DOWNLOAD_URL_FORMAT.format(
        resource_id=self.resource_id,
        key=CONFIG['apikey'])

  @property
  def thumbnail_url(self):
    return '/thumbnails/{}'.format(self.resource_id)

  @classmethod
  def create_thumbnail_url(cls, resource_id):
    return THUMBNAIL_URL_FORMAT.format(
        resource_id=resource_id,
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

  def create_blob_key(self, thumbnail=False):
    if thumbnail:
      return blobstore.create_gs_key('/gs{}'.format(self.gcs_thumbnail_path))
    return blobstore.create_gs_key('/gs{}'.format(self.gcs_path))

  def to_message(self):
    message = messages.AssetMessage()
    message.ident = self.ident
    message.download_url = self.download_url
    message.title = self.title
    message.size = self.size
    message.thumbnail_url = self.thumbnail_url
    message.metadata = self.metadata
    return message
