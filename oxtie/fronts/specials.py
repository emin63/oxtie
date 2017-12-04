"""Specialized examples of frontends with more features.
"""

import os
import tempfile
import re
import doctest

from oxtie.fronts import nums
from oxtie.backs import aws, simple


class ColValidatorMixin(object):  # pylint: disable=too-few-public-methods
    """Mix-in to require certain columns in something with frame property.

    The ColValidatorMixin illustrates how to have a validate method
    which verifies that a frame property with certain columns exists.

    **IMPORTANT**: Your mixins must come before other things to get called.

    To illustrate, we do some setup to create an example pandas DataFrame:

>>> import pandas, io, logging
>>> from oxtie.fronts import specials, nums
>>> csv = ('%c'%10).join(['event_date,estimate,reported,period_date',
...     '2017-10-01,,,2017/9',  # Create some sample data
...     '2017-07-01,0.17,0.15,2017/6',''])
>>> logging.info('IMPORTANT: Mixins go before other classes to work right.')
>>> class RequireEstimateExample(specials.ColValidatorMixin, nums.SimpleFrame):
...     required_cols = set(['estimate']) # Set of col names we require.
...

    Next we deserialize from the CSV representation:

>>> f = RequireEstimateExample.deserialize_body_csv(
...       {'_name': 'test'}, {'__csv': csv}, None)
>>> f.frame.to_csv() == csv  # Verify deserialized version matches.
True

    Finally, we illustrate what happens if we try to deserialize from
    a version which is missing some columns. Note that this is kind of a nice
    way to build some validation into how you save and load data. Here we
    are just taking CSV data that may have been generated from who knows where
    and trying to deserialize it into an instance of our RequireEstimateExample
    class.

>>> try:
...     RequireEstimateExample.deserialize_body_csv({'_name': 'test'},
...        {'__csv': f.frame[['reported']].to_csv()},  # Only provide 1 column
...        None)
... except ValueError as exc:
...     print('Got ValueError: %s' % str(exc))
...
Got ValueError: Missing columns: [estimate]

    """

    # Set required_cols to a set of strings to check.
    required_cols = set()

    def validate(self):
        """Validate that required_cols are in self.frame
        """
        super().validate()
        frame = getattr(self, 'frame', None)
        if frame is None:
            raise ValueError('Missing columns %s since no frame' % ', '.join(
                self.required_cols))
        cols = set(list(self.frame))
        missing = sorted(self.required_cols - cols)
        if missing:
            raise ValueError('Missing columns: [%s]' % ', '.join(missing))


class ColRegexpMixin(object):  # pylint: disable=too-few-public-methods

    # Set required_cols to a set of strings to check.
    col_regexps = []

    def validate(self):
        """Validate that required_cols are in self.frame
        """
        super().validate()
        frame = getattr(self, 'frame', None)
        if frame is None:
            raise ValueError('Missing columns %s since no frame' % ', '.join(
                [c[0] for c in self.col_regexps]))
        for col_name, c_re in self.col_regexps:
            if col_name not in self.frame:
                raise ValueError('Missing required column %s' % col_name)
            if c_re is None:
                continue  # Just verified that column is present
            c_re_c = re.compile(c_re)
            for date, item in self.frame[col_name].iteritems():
                if not c_re_c.match(item):
                    raise ValueError(
                        'In column %s, index %s, item %s fails regexp %s' % (
                            col_name, date, item, c_re))


class S3BackendMixin(object):  # pylint: disable=too-few-public-methods
    """Backend mixin to store to S3.

    This class provides a mixin you can include in defining a frontend
    which will store to S3 by default. You can set the default_bucket
    class property to choose your bucket and the default_category class
    property to set a prefix `directory` in your S3 bucket if you want.
    """

    default_bucket = 'oxtie'  # Set to string indicating your S3 bucket.
    default_category = ''      # Set to string indicating a prefix (can be '')

    @classmethod
    def get_backend(cls, backend=None):
        """Create an S3Backend instance.
        """
        return backend if backend else aws.S3Backend(
            category=cls.default_category, bucket_name=cls.default_bucket)


class TempFileBackend(simple.FileBackend):
    """Backend to store to temporary file.

>>> import pandas  # So we can make a dataframe.
>>> from oxtie.fronts import specials  # Illustrate special example
>>> frame = pandas.DataFrame({'estimate': [.17, None]}, # Make some
...     index=['2017-07-01', '2017-10-01'])             # sample data
>>> backend=specials.TempFileBackend()
>>> f = specials.nums.SimpleFrame(name='test', backend=backend, frame=frame)
>>> f.save()
>>> g = backend.load('test', allow_load=True)
>>> g.frame.to_csv() == f.frame.to_csv()
True
    """

    def __init__(self, root=None, *args, **kwargs):
        if root is None:
            root = os.path.dirname(tempfile.mktemp())
        super().__init__(root, *args, **kwargs)


class EarningsFrame(ColValidatorMixin, S3BackendMixin, nums.SimpleFrame):
    """Example to show how you could save/load earnings data to/from S3.

    The EarningsFrame illustrates how to sub-class nums.SimpleFrame and
    use some simple mix-ins to create a nice object which can use a
    Pandas DataFrame to store stock earning data which is easy to save/load
    to/from Amazon S3.

    To illustrate, we do some setup to create an example pandas DataFrame:

>>> import pandas, io
>>> from oxtie.fronts import specials
>>> frame = pandas.DataFrame({'estimate': [.17, None], 'reported': [.15, None],
...     'period_date': ['2017/6', '2017/9']},
...     index=['2017-07-01', '2017-10-01'])
>>> f = specials.EarningsFrame('test', frame=frame)

    Now you would just call `f.save()` to save to s3.
    To load from s3, you would just call `specials.EarningsFrame.load('test')`.
    Note that you will need to have the S3 bucket specified in
    the `specials.EarningsFrame.default_bucket` class variable created and
    have your S3 credentials in ~/.aws/config for this to work.
    """

    default_bucket = 'oxtie'
    default_category = 'data/earnings'
    required_cols = set(['period_date', 'estimate', 'reported'])


if __name__ == '__main__':
    doctest.testmod()
    print('Finished tests')
