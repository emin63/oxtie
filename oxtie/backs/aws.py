"""Backend to write to various Amazon Web Services (AWS) backends.

See the S3Backend and DynamoBackend classes.
"""

import io
import logging

import boto3
import botocore

from oxtie.backs import base as back_base


class S3Backend(back_base.Backend):
    """Backend for Amazon S3.

    See docs for __init__.
    """

    def __init__(self, category, bucket_name, *args, **kwargs):
        """Initializer.

        :param category:  Optional string prefix to use as `directory`. You
                          can leave this as '' to not use any prefix or
                          provide something like 'my/path/to/stuff' which
                          will be prepended like a directory to the name
                          of something to save.

        :param bucket_name:  AWS bucket name. You must have already created
                             this and have your ~/.aws/config set to give
                             permissions.

        :param *args, **kwargs:    As for base.Backend constructor (e.g.,
                                   front_cls, allow_load, etc.)

        """
        super().__init__(*args, **kwargs)
        self.category = category
        self.bucket_name = bucket_name
        self.my_s3 = boto3.session.Session().resource('s3')

    def prep_key(self, uid):
        """Convert a uid to key to use in saving/loading data.

        Takes a Frontend instance or result of calling get_key() on
        a Frontend and returns a string key to use in creating a
        file name.
        """
        if not isinstance(uid, dict):
            uid = uid.get_key()
        keypath = '/'.join(['%s=%s' % (n, uid[n]) for n in sorted(uid)])

        if self.category:
            keypath = '%s/%s' % (self.category, keypath)

        return keypath

    def write_serialized(self, front, serialized):
        """Implement as required by parent Backend clas.
        """
        key = self.prep_key(front)
        result = self.my_s3.Bucket(self.bucket_name).put_object(
            Key=key, Body=serialized)
        return result

    def get_read_stream(self, uid):
        """Implement as required by parent Backend class.
        """
        key = self.prep_key(uid)
        try:
            obj = self.my_s3.Object(self.bucket_name, key)
            raw = obj.get()['Body']
        except botocore.exceptions.ClientError as problem:
            logging.info('Got error in s3 operation: %s', str(problem))
            response = getattr(problem, 'response', None)
            if response is None:
                raise
            code = response.get('Error', {}).get('Code', None)
            if code is None:
                raise
            if code == 'NoSuchKey':
                raise KeyError(key)
            raise

        return raw

    def delete(self, uid):
        """Implement as required by parent Backend class.
        """
        key = self.prep_key(uid)
        self.my_s3.Object(self.bucket_name, key).delete()


class DynamoBackend(back_base.Backend):
    """Backend for saving data to AWS DynamoDB.

    Since DynamoDB requires a primary key and optionall a secondary key and
    no more, the __init__ method takes a special key_fields dict as input
    to determine how to create the key from the facets.

    See docs for __init__ for details.
    """

    default_key_fields = None
    key_sep = '#'
    default_table_name = None

    def __init__(self, table_name=None, key_fields=None, *args, **kwargs):
        """Initializer.

        :param table_name=None:  String name of dyanmodb table to use. This
                                 must already exists and you must have
                                 ~/.aws/config set to provide permissions.
                                 If None, we use self.default_table_name

        :param key_fields:       Dictionary with either one or two strnig keys
                                 and values being sequences of strings which
                                 specify the items in a key dictionary
                                 are part of which key. These will be joined
                                 with the separator from cls.key_sep to form a
                                 string for the primary key and secondary keys.
                                 If None, then we use cls.default_key_fields.

        :param *args, **kwargs:    As for base.Backend constructor (e.g.,
                                   front_cls, allow_load, etc.)
        """
        super().__init__(*args, **kwargs)
        self.key_fields = dict(key_fields) if key_fields is not None else (
            dict(self.default_key_fields))
        self.table_name = table_name if table_name is not None else (
            self.default_table_name)
        # Need session to keep things semi thread safe
        session = boto3.session.Session()
        self.dynamodb = session.resource('dynamodb')

    def prep_key(self, uid):
        """Convert a uid to key to use in saving/loading data.

        Takes a Frontend instance and calls get_key() or result of get_key().
        It then converts that into a dictionary reperesenting the
        database key.
        """
        if not isinstance(uid, dict):
            uid = uid.get_key()
        uid = dict(uid)
        key = {}
        assert len(self.key_fields) in (1, 2), (
            'Wrong # of key fields=%i.  Must be 1 or 2' % len(self.key_fields))
        for name, key_list in self.key_fields.items():
            key[name] = self.key_sep.join([uid.pop(n) for n in key_list])
        if uid:
            raise ValueError('Did not use all elements of uid in key: %s' % (
                str(uid)))

        return key

    def write_serialized(self, front, serialized):
        """Implement as required by parent Backend clas.
        """
        table = self.dynamodb.Table(self.table_name)
        data = self.prep_key(front)
        data['object'] = serialized
        table.put_item(Item=data)

    def get_read_stream(self, uid):
        """Implement as required by parent Backend clas.

        The uid argument can be an instance of a Frontend or the result of
        calling get_key on an instance of FrontEnd.
        """
        table = self.dynamodb.Table(self.table_name)
        key = self.prep_key(uid)
        my_obj = table.get_item(Key=key)
        if my_obj is None or 'Item' not in my_obj:
            raise KeyError(key)
        result = io.BytesIO(my_obj['Item']['object'].value)
        return result

    def delete(self, uid):
        """Implement as required by parent Backend clas.
        """
        table = self.dynamodb.Table(self.table_name)
        key = self.prep_key(uid)
        table.delete_item(Key=key)
