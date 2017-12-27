"""Basic specification for a frontend.

See docs on Frontend class for further information.
"""

import doctest

import msgpack
import oxtie


class Frontend(object):
    """Class specifying the main interface for a frontend and some utils.

    All other frontend implementations shall inherit from this.

    The following illustrates example usage. First we do imports:

>>> import tempfile, os, shutil
>>> from oxtie.fronts import base
>>> from oxtie.backs import simple

    Next we create an instance of simple FileBackend and give it a
    root directory so it knows where to store things.

>>> backend = simple.FileBackend(root=tempfile.mkdtemp(suffix='.oxtie'))

    Now we crate an instance of our Frontend object with the name
    'test' and some other facets, and tell it to use our backend.

>>> f = base.Frontend({'name': 'test', '_last_update': '2017', '_bar': 'baz'},
...                   backend)

    We could have sub-classed base.Frontend to have additional properties
    or we can just add them whenever we like:

>>> f.big_data = '*' * 10  # You can add properties and they will get saved

    Now we simply call the save method and the backend saves it. The nice
    thing here is that the f.save() could would work equally well with any
    backend. This gives you a lot of flexbility since you can choose or
    change your backend later.

>>> f.save()

    We can load just the header for our saved object if desired. This is
    usually very cheap and fast. The header also provides the facets
    (which should be kept small) so you can load the header to decide if
    you want to do further processing:

>>> hdr = backend.load({'name': 'test'}, only_hdr=True) # Fast load just header
>>> hdr['_facets']['_last_update']
'2017'

    Imagine we do want to load the item. We can just call the backend.load
    method. Here we explicitly tell the backend what python class to load
    the data into. Later we can explore some clever tricks so that you
    don't need to specify the frontend because the backend can read it
    from the header and find the right class itself.

>>> g = backend.load({'name': 'test'}, front_cls=base.Frontend)
>>> f.big_data == g.big_data  # Verify things worked
True

    If we wanted to explicitly lookup the frontend class, we could do:

>>> import importlib
>>> mod = importlib.import_module(hdr['mod_name'])
>>> h = backend.load({'name': 'test'}, front_cls=getattr(mod, hdr['cls_name']))
>>> h.big_data == f.big_data
True

    If we are OK with implicitly loading modules we can just specify
    `allow_load=True` and things will be loaded implicitly. This is
    not done by default since loading arbitrary modules is potentially
    a security risk and it might get confusing if your paths are not set right.

>>> i = backend.load({'name': 'test'}, allow_load=True)
>>> i.big_data == f.big_data
True

    Now cleanup the temporary directory we used for this demo.

>>> shutil.rmtree(backend.root)

    """

    def __init__(self, facets, backend=None):
        """Initializer.

        :param facets:       Dictionary of "facets" for the item. Ideally it
                             should be a dictionary of string keys and
                             simple types (e.g., int, float, string, dates)
                             as values. Which can be serialized with msgpack.
                             An important feature of the facets is that
                             they are packed/unpacked in the header so you
                             can easily/quickly assess whether to do a full
                             unpack or not or scan packed items. The KEY
                             for the object must come from the facets.

        :param backend=None: Instance of a backend to use in saving. This can
                             be None if you don't intend to save it or if you
                             want the get_backend method to choose it laer.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Main initializer for a Frontend. Sub-classes will almost
                  certainly have additional properties to store.
        """
        self._facets = facets
        self._backend = backend

    @classmethod
    def facets2key(cls, facets):
        """Take in the facets dict and return the key dict.

        The `facets` input is a dictionary with string keys and values such
        that str(VALUE) is stable (i.e., not something like a float which may
        have a different string representation on different systems).

        This function shall return a dict which represents the unique key
        identifying this object. By default, we just return everything in
        `facets` where the key name does not begin with an underscore, but
        sub-classes may want to do something more intelligent like return only
        `facets['name']` or `'%s/%s' % (facets['category'], facets['name'])`.

        The returned value must satisfy the following criteria:

            1. It must uniquely identify the object.
            2. It must be a dictionary with string keys and string values.
            3. The algorithm to get the key from the facets must be a stable
               function of only the input facets (e.g., it should not call
               random, or use values in the object outside the header).

        This key is used to identify the object when saving and loading
        to and from the backend.
        """
        dummy = cls  # Sub-classes may want to use cls, but we ignore it here
        return {n: v for n, v in facets.items() if n and n[0] != '_'}

    def get_key(self):
        """Return a dict representing key for this object.

        The default version simply does self.facets2key(self.get_facets_dict())
        Sub-classes may which to override this or just override facets2key.
        """
        return self.facets2key(self.get_facets_dict())

    def get_facets_dict(self):
        """Return a reference to the self._facets dict set in __init__.
        """
        return self._facets

    def serialize(self, body_mode=None):
        """Serialize self into a string.

        :param mode=None:   Optional string indicating mode. If None, then
                            we use self.get_default_body_mode().

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  A serialized representation of self.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Workhorse to do the serialization before we save something.
                  You generally do **NOT** need to override this method in
                  a sub-class. Instead, you can implement a new mode and
                  provide a serialize_body_<MODE> method which this method will
                  lookup and call.

                  By default we always serialize the header with msgpack but
                  allow serializing the body in some other mode. This is so
                  that in deserializing we can always unpack the header using
                  msgpack and then decide what to do next.
        """
        if body_mode is None:
            body_mode = self.get_default_body_mode()
        hdr = self.serialize_header()
        bfunc = getattr(self, 'serialize_body_%s' % body_mode, None)
        if bfunc is None:
            raise ValueError('Invalid body serialization mode %s' % body_mode)

        body = bfunc()  # pylint: disable=not-callable
        return hdr + msgpack.packb(body, use_bin_type=True)

    def serialize_header(self):
        """Serialize the header.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  A seraizlied version of the header.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  We generally want to serialize the header and body
                  separately. This is because:

             1. We want the header in a simple standard format that is
                easily read. (We use msgpack by default). While there may
                be reasons to use different serialization for the body, it is
                essential that you can *READ* the header easily so you know
                what is going on with the body.
             2. You generally want the header to be short and quick so you
                can get a little information before deciding whether to
                read/parse the body.

        """
        header = {'body_mode': 'msgpack', '__oxtie_version__': oxtie.version,
                  '_facets': self._facets,
                  'mod_name': self.__module__,
                  'cls_name': self.__class__.__name__}
        return msgpack.packb(header, use_bin_type=True)

    def serialize_body_msgpack(self, do_pack=True, skips=()):
        """Serialize the body in msgpack format and return it.

        :param do_pack=True: If True, return body in msgpack format, otherwise
                             return the dictionary we would pack but leave it
                             as a dict in case the caller wants to modify it
                             before serializing. This is useful for
                             sub-classes.

        :param skips=(): Tuple of strings indicating properties to skip. We
                         always skip _backend and _facets since
                         those eitehr go in the header or are not supposed
                         to be serialized. If you implement a sub-class that
                         serializes some properties in a special way, you can
                         pass in the name of properties you handle serparately
                         here.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Bytes representing serialized version of the body of self.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Meant to be called by serialize method and not directly.

        The default implementation serializes everything in self.__dict__
        except for the given `skips` which are serialized in the header.
        If you have special properties, you may want to override this method
        to serialize your special items differntly.

        NOTE: If you do something special here, you may also need to
              override deserialize_body_msgpack as well.
        """
        skips = set(skips).union(('_backend', '_facets'))
        body = {n: v for n, v in self.__dict__.items() if n not in skips}
        if do_pack:
            body = msgpack.packb(body, use_bin_type=True)
        return body

    @classmethod
    def get_default_body_mode(cls):
        """Return string indicating default serialization body mode.
        """
        return 'msgpack'

    @classmethod
    def deserialize(cls, packed, backend=None, body_mode=None, only_hdr=False):
        """Basically the opposite of serialize: make instance from data.

        :param packed:   The packed serialized representation produced by
                         the serialize method.

        :param backend:  The backend that you would like to use to be able
                         to store this instance. You can leave this as None
                         if you just want to use the item not store it again.

        :param body_mode=None:  Optional string mode as with serialize method.
                           If None, we first look at the body_mode in header
                           and if that is not use get_default_body_mode. You
                           can implement your own deserialize_body_<BODY_MODE>
                           method so you don't have to override this method.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   Instance of this class matching the one which was
                   serialized into packed.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Inverse of serialize: produce an object from data.

                   Note: you generally do *NOT* want to override this but
                   instead override deserialize_body_* methods.

        """
        if only_hdr:
            return cls.packed_to_hdr(packed)
        hdr, body = cls.packed_to_hdr_and_body(packed)
        if body_mode is None:
            body_mode = hdr.get('body_mode', None)
        if body_mode is None:
            body_mode = cls.get_default_body_mode()
        myfunc = getattr(cls, 'deserialize_body_%s' % body_mode, None)
        if myfunc is None:
            raise ValueError('Invalid serialization body_mode %s' % body_mode)
        else:
            result = myfunc(hdr, body, backend)  # pylint: disable=not-callable
            result.validate()
            return result

    @classmethod
    def packed_to_hdr_and_body(cls, packed):
        """Unpack the header and body from a packed serialized representation.

        :param packed:     The packed serialized representation.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  The pair (hdr, body) where hdr is a dict containing
                  header information about the stored item and body is
                  the (still serialized) body.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Unpack the header and get the body. You will probably
                  still need to deserialize the body. This is a helper
                  method and not meant to be called directly.

        """
        dummy = cls
        unpacker = msgpack.Unpacker(packed, encoding='utf-8')
        hdr, body = unpacker
        return hdr, body

    @classmethod
    def packed_to_hdr(cls, packed):
        """Unpack the header from a packed serialized representation.

        :param packed:     The packed serialized representation.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  A dict representing the header information.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Quickly get just the header from the packed representation
                  so we can decide to do next.

        """
        unpacker = msgpack.Unpacker(packed, encoding='utf-8')
        return unpacker.unpack()

    @classmethod
    def deserialize_body_msgpack(cls, hdr, body, backend, skips=None):
        """Deserialize and create instance from packed version.

        :param hdr:       Dictionary for the header of the object.

        :param body:      Either Bytes representing msgpack representation of
                          the body or a dict. The latter is sometimes useful
                          for sub-classes which unpack some things themselves.

        :param backend:   Instance of backend to deserialize.

        :param skips=None:  Optional dictionary with string keys. Any key
                            in skips will *NOT* be deserialized into the
                            result but have its data placed into skips for
                            the caller to handle. This is useful for
                            sub-classes which are overriding this.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

         :return:   Instance of cls.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Inverse of serialize.  Meant to be called by deserialize
                   method when mode='msgpack'. Not meant to be called directly.

                   The default implementation takes the values in body
                   and puts them into the __dict__ for the new item.

        """
        skips = skips if skips else {}
        result = cls(hdr.get('_facets', {}), backend)
        if isinstance(body, dict):
            my_dict = body
        else:
            my_dict = msgpack.unpackb(body, encoding='utf-8')
        for name, value in my_dict.items():
            if name in skips:
                skips[name] = value
            else:
                setattr(result, name, value)

        return result

    def validate(self):
        """Simple function to make sure self is valid.

        Should return True if valid or raise a ValueError otherwise.
        This is useful as a check to make sure things are deserialized
        correctly.
        """
        dummy = self
        return True

    @classmethod
    def get_backend(cls, backend=None):
        """Choose a backend instance.

        :param backend=None:  If provided, use this.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Return backend if it is not None, otherwise try
                  to choose a reasonable bakend somehow.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Sub-clases can override this to provide a default backend.
        """
        return backend

    def save(self, backend=None):
        """Save an instance of self on the specified backend.

        :param backend=None:   Optional backend to use. If this is None,
                               we try to use self._backend (which is the
                               backend specified in __init__) and if that
                               fails we call self.get_backend().
        """
        backend = backend if backend else self.get_backend(self._backend)
        backend.save(self)

    @classmethod
    def load(cls, key, backend=None, only_hdr=False):
        """Load an instance of self with the given key from specified backend.

        :param key:    A dictionary with string keys and string values as
                       produced by the get_key method or a Frontend instance.

        :param backend=None:   The backend we want to load from. If this is
                               None, we call get_backend() to try to get one.

        :param only_hdr=False: Whether to only load the header (in which case
                               we do not need a backend).

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   A new instance of self corresponding to the one we
                   `save`-ed previously if only_hdr is False or a dictionary
                   representing the header if only_hdr is True.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Inverse of save method; load it back.

        """
        backend = cls.get_backend(backend)
        new_item = backend.load(key, only_hdr=only_hdr, front_cls=cls)
        return new_item

    def delete(self, backend=None):
        """Delete self from the backend.

        :param backend=None:   The backend we want to delete from. If this is
                               None, we call get_backend() to try to get one.

        The current instance is not changed; only backend representation is
        deleted. This should only be called if the backend actually is
        storing self.
        """
        backend = backend if backend else self.get_backend(self._backend)
        backend.delete(self)

if __name__ == '__main__':
    doctest.testmod()
    print('Finished Tests')
