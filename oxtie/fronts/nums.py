"""Simple implementations of basic storage methods for numeric data.

See the SimpleFrame class and its documentation to get started.
"""

import doctest
import io

import msgpack
import numpy
import pandas

from oxtie.fronts import base


def msgpack_encoder(obj):
    """Simple function to help with msgpack serialization.

    :param obj:    Object to serialize.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    :return:    Either obj or a converted version which can be serialized.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:    Handle serializaing tricky things like numpy.bool_

    """
    if isinstance(obj, numpy.bool_):
        return bool(obj)
    return obj


class SimpleFrame(base.Frontend):
    """Storage of a pandas DataFrame

    The SimpleFrame class provides an oxtie front end to hold
    a pandas DataFrame. As with all front ends, you instantiate it
    with a name along with optional attributes and an optional backend.
    In addition, you can provide a frame which is a pandas DataFrame.

    The SimpleFrame knows how to intelligently store pandas DataFrame
    objects on a backend. It does things like handle specials types
    like numpy.bool_, Pandas Timestamp objects, etc.

    The following illustrates example usage:

    First we import various things and setup our DataFrame.

>>> import tempfile, os, shutil, pandas
>>> from oxtie.fronts import nums
>>> frame = pandas.DataFrame({'estimate': [.17, None], 'reported': [.15, None],
...     'period_date': ['2017/6', '2017/9']},
...     index=['2017-07-01', '2017-10-01'])

    Next we specify setup a backend that can save to a local file.

>>> from oxtie.backs import simple
>>> backend = simple.FileBackend(root=tempfile.mkdtemp(suffix='.oxtie'))

    Now we can create SimpleFrame instance.

>>> f = nums.SimpleFrame('test', backend=backend, frame=frame)
>>> f.more = '*' * 10  # Add some more data in a property to save.

    When we are ready, we can save the SimpleFrame frame.

>>> f.save()

    Later, we can reload the SimpleFrame simply by using its name.

>>> g = nums.SimpleFrame.load('test', backend=backend)

    Finally we verify that the loaded data matched the original and
    then cleanup.

>>> all(g.frame == f.frame) and f.more == g.more
True
>>> f.delete() # delete f from the backend.
>>> os.listdir(backend.root) # verify it was deleted.
[]
>>> shutil.rmtree(backend.root) # remove the temp directory we were using.
    """

    def __init__(self, name, attributes=None, backend=None, frame=None):
        """Initializer.

        :param name:  String name as for base.Frontend.

        :param attributes=None:   Attribtute dict as for base.Frontend.

        :param backend=None:    Optional backend as for base.Frontend.

        :param frame=None:    Optional pandas DataFrame.

        """
        super().__init__(name, attributes, backend)
        self.frame = frame

    def help_serialize_body(self):
        """Serialization helper.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Data to serialize data frame for self in dictionary form.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  This method basically flattens self.frame into things
                  like the columns in the dataframe in self.frame, the
                  index, etc.  This is helpful since most
                  serialization systems are easier to apply to the
                  flattened pieces. Thus the way to write a new
                  serialize_body_* method is usually to first call
                  help_serial and then serialize the resulting
                  dictionary.

        SEE ALSO: help_deserialize_body

        """
        result = {'__columns': list(self.frame), '__index': []}
        idx = result['__index']
        result['__data'] = {n: [] for n in list(self.frame)}
        data_cols = [result['__data'][n] for n in list(self.frame)]
        my_tz = self._attributes.get('timezone', None)
        for item in self.frame.itertuples():
            idx_item = item[0]
            if my_tz is not None and hasattr(idx_item, 'tz_localize'):
                idx_item = idx_item.tz_localize(my_tz)
            if not isinstance(idx_item, str):
                idx_item = idx_item.timestamp()
            idx.append(idx_item)
            for dcol, value in zip(data_cols, item[1:]):
                dcol.append(value)
        return result

    def serialize_body_msgpack(self, do_pack=True, skips=None):
        """Implement serialization using msgpack protocol.

        This is meant to be called via serialize('msgpack') not directly. It
        overrides the serialize_body_msgpack to handle the pandas DataFrame
        intelligently.
        """
        if skips:
            skips = set(skips).union(('frame', ))
        else:
            skips = ('frame', )
        body = super().serialize_body_msgpack(do_pack=0, skips=skips)
        frame_body = self.help_serialize_body()
        assert not set(body).intersection(frame_body), (
            'Conflict in names for serializing body and frame')
        body.update(frame_body)
        if do_pack:
            body = msgpack.packb(body, use_bin_type=True,
                                 default=msgpack_encoder)
        return body

    @classmethod
    def deserialize_body_msgpack(cls, hdr, body, backend, skips=None):
        """Deserialize and create instance from packed version.

        Implements deserialize_body_msgpack as described in parent
        class with special handling for data frame.
        """
        skips = skips if skips else {}
        for name in ['__columns', '__index', '__data']:
            if name in skips:
                raise ValueError('Cannot skip %s in restoring frame' % name)
            skips[name] = None
        basic = super().deserialize_body_msgpack(hdr, body, backend, skips)
        return cls.help_deserial(basic, skips)

    @classmethod
    def deserialize_body_csv(cls, hdr, body, backend, skips=None):
        """Deserialize and create instance from packed CSV version.

        Implements deserialize_body_csv similarly to deserialize_body_msgpack.
        """
        skips = skips if skips else {}
        for name in ['__csv']:
            if name in skips:
                raise ValueError('Cannot skip %s in restoring frame' % name)
            skips[name] = None
        basic = super().deserialize_body_msgpack(hdr, body, backend, skips)
        wrap = io.StringIO(skips['__csv'])
        frame = pandas.read_csv(
            wrap, parse_dates=[0], infer_datetime_format=True, index_col=0)
        basic.frame = frame
        basic.validate()
        return basic

    @classmethod
    def help_deserial(cls, basic, skips):
        """Helper to deserialize.

        :param basic:     The basic object produced by the initial
                          deserialization step but with the frame not yet

        :param skips:     Dictionary with data elements that were skipped
                          in the basic deserialization and should be processed.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   Fully deserialized instance.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   This takes a basic object which is mostly deserialized
                   except for the pands DataFrame and handles the DataFrame.
                   This lets us split the DataFrame handling code from
                   the generic deserialization code.

        """
        idx = cls.deserialize_timestamps(
            skips['__index'], basic.get_attr_dict().get('timezone'))
        fdict = {}
        for cname in skips['__columns']:
            cval = skips['__data'][cname]
            if cval:
                fdict[cname] = cval
            else:
                fdict[cname] = [None]*len(idx)

        # Explicitly specify columns so we get ordering as desired.
        frame = pandas.DataFrame(fdict, index=idx, columns=skips['__columns'])
        basic.frame = frame
        basic.validate()
        return basic

    @classmethod
    def deserialize_timestamps(cls, data, my_tz=None):
        idx = []
        for idx_item in data:
            if isinstance(idx_item, float):
                idx_item = pandas.Timestamp.fromtimestamp(idx_item)
            else:
                idx_item = pandas.Timestamp(idx_item)
            if my_tz is not None:
                idx_item = idx_item.tz_localize(my_tz)
            idx.append(idx_item)
        return idx

    @staticmethod
    def _regr_test():
        """
>>> import tempfile, os, shutil, pandas, random
>>> from oxtie.fronts import nums
>>> from oxtie.backs import simple
>>> random.seed(123)  # Make tests repeatable
>>> backend = simple.FileBackend(root=tempfile.mkdtemp(suffix='.oxtie'))
>>> idx = [pandas.Timestamp(
...     '2017-01-%s' % str(i).zfill(2)) for i in range(1,15)]
>>> estimate = [random.gauss(0, 1) for i in idx]
>>> reported = [e + .05 * random.gauss(0, 1) for e in estimate]
>>> p = pandas.DataFrame({'estimate': estimate, 'reported': reported},
...     index=idx)
>>> f = nums.SimpleFrame('test', {}, backend, p)
>>> f.more = '*' * 10  # Add some more data in a property to save.
>>> f.save()
>>> g = backend.load('test', allow_load=True)
>>> all(g.frame == f.frame) and f.more == g.more
True
>>> shutil.rmtree(backend.root)
"""

    @staticmethod
    def _regr_test_fromcsv():
        """Test reading in from a CSV since that has a few differences.

    Using pandas.read_csv produces a DataFrame with the following potential
    issues:

       1. Booleans become numpy.bool_ which may not be serializable without
          some tricks.
       2. Column ordering may end up different.

>>> import tempfile, os, shutil, io, pandas, msgpack
>>> from oxtie.fronts import nums
>>> from oxtie.backs import simple
>>> backend = simple.FileBackend(root=tempfile.mkdtemp(suffix='.oxtie'))
>>> data = io.StringIO(('%c'%10).join([
...    'event_date,estimate,period_date,reported,confirmed',
...    '10/1/2017,,2017/9,,FALSE',
...    '7/1/2017,0.17,2017/6,0.15,TRUE']))
>>> p = pandas.read_csv(data, index_col=0, parse_dates=[0])
>>> f = nums.SimpleFrame('test', {}, backend, p)
>>> f.more = '*' * 10  # Add some more data in a property to save.
>>> f.save()
>>> g = backend.load('test', allow_load=True)
>>> all(g.frame == f.frame) and f.more == g.more
True

    As an aside, you can use the deserialize_body_csv method to create
    a nums.SimpleFrame instance directly from a CSV representation without
    having to call pandas.read_csv first:

>>> cbody = {'__csv': f.frame.to_csv()}
>>> h = nums.SimpleFrame.deserialize_body_csv({'_name': 'test'}, cbody, None)
>>> all(h.frame == f.frame)
True

    Now clean up

>>> shutil.rmtree(backend.root)
"""

if __name__ == '__main__':
    doctest.testmod()
    print('Finished Tests')
