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

        This can take a string name or a Frontend instance and call get_name().
        """
        if isinstance(uid, str):
            name = uid
        else:
            name = uid.get_name()

        if self.category:
            key = '%s/%s' % (self.category, name)
        else:
            key = name

        return key

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

    See docs for __init__ for details.
    """

    default_key_name = None
    default_range_key = None
    default_range_value = None

    def __init__(self, table_name=None, key_name=None, range_key=None,
                 *args, **kwargs):
        """Initializer.

        :param table_name=None:  String name of dyanmodb table to use. This
                                 must already exists and you must have
                                 ~/.aws/config set to provide permissions.
                                 If None, we use self.default_table_name

        :param key_name=None:    Name of the primary key field. We use
                                 self.default_range_key if key_name is None.

        :param range_key=None:   Optional name of the secondary key field.
                                 This is a little tricky since most Backend
                                 sub-classes do not use secondary keys. If
                                 your table does have range keys, you would
                                 specify the field name of the range key here.
                                 When saving a Frontend instance, we look for
                                 get_attr_dict()[range_key] to get the range
                                 key. See also the docs for get_read_stream
                                 for loading something with a range_key.

        :param *args, **kwargs:    As for base.Backend constructor (e.g.,
                                   front_cls, allow_load, etc.)
        """
        super().__init__(*args, **kwargs)
        self.key_name = key_name if key_name is not None else (
            self.default_key_name)
        self.range_key = range_key if range_key is not None else (
            self.default_range_key)
        self.table_name = table_name if table_name is not None else (
            self.default_table_name)
        # Need session to keep things semi thread safe
        session = boto3.session.Session()
        self.dynamodb = session.resource('dynamodb')

    def prep_key(self, uid):
        """Convert a uid to key to use in saving/loading data.

        This can take a string name or a Frontend instance and call get_name().

        For this class, the uid can also be a pair of the form

                (HASH_KEY, RANGE_KEY)

        since if the table supports range keys, you will need to specify both.
        """
        if isinstance(uid, str):
            key = {self.key_name: uid}
            if self.range_key is not None:
                key[self.range_key] = self.default_range_value
        elif isinstance(uid, (tuple, list)):
            assert self.range_key is not None, (
                'No range_key specified in __init__')
            assert len(uid) == 2, (
                'Expected (hash_key, range_key) got %s' % (str(uid)))
            key = {self.key_name: uid[0],
                   self.range_key: uid[1]}
        else:
            key = {self.key_name: uid.get_name()}
            if self.range_key is not None:
                key[self.range_key] = uid.get_attr_dict().get(
                    self.range_key, self.default_range_value)
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

        This can take a string name or a Frontend instance and call get_name().

        For this class, the uid can also be a pair of the form

                (HASH_KEY, RANGE_KEY)

        since if the table supports range keys, you will need to specify both.
        Thus when calling load(uid) you can specify (HASH_KEY, RANGE_KEY)
        to do the load.
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
