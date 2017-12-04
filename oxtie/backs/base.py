"""Basic specification for backend.

This file provides the basic interface that all backends shall implement.
See the Backend class for further information.
"""

import importlib

from oxtie.fronts import base as front_base


class Backend(object):
    """Class specifying main interface for backend and providing a few utils.

    All other backend implementations shall inherit from this and follow
    this model.
    """

    def __init__(self, front_cls=None, allow_load=False):
        """Initializer.

        :param front_cls=None:  Class to call to create an instance of an
                                oxtie front end. Calling
                                `front_cls.deserialize(raw, self)` shall
                                return an instance of
                                `oxtie.fronts.base.Frontend`. This
                                `front_cls` argument can be None (e.g.,
                                if `allow_load` is True or if you plan to
                                deal with this later).

        :param allow_load=False: Whether to allow dynamic import of the
                                 front_cls at load time. This is technically
                                 a security risk since you are dynamically
                                 loading a python module so it is disabled
                                 by default. Provided you trust the modules
                                 on your system or the backend you are loading
                                 from, though, it can be relatively safe.
        """
        self.front_cls = front_cls
        self.allow_load = allow_load

    def save(self, front):
        """Save the given instance to the backend.

        :param front:  Instance of `oxtie.fronts.base.Frontend` to save.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  This method saves the given front instance to the backend
                  so that calling self.load(front.name) will return something
                  matching front. Sub-classes shall implement this.

                  Generally sub-classes do not need to override this but
                  can instead override write_serialized instead.

        """
        serialized = front.serialize()
        self.write_serialized(front, serialized)

    def load(self, uid, only_hdr=False, front_cls=None, allow_load=None):
        """Load a saved instance from the backend.

        :param uid:    Either a string name or a Frontend instance or some
                       other unique id that the backend supports for loading
                       an item. A string or Frontend shall always be supported
                       while other forms of uid depend on the backend.

        :param only_hdr=False:  If True, only deserialize the header which
                                is faster and cheaper.

        :param front_cls=None:  The class we are deserializing. You can leave
                                this as None if only_hdr is True or if you
                                set allow_load to True (see below).

        :param allow_load=None: If this is None then use self.allow_load.
                                If allow_load evaluates to True, then we will
                                try to dynamically load the module and class
                                that the named object was serialized from.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Instance of `oxtie.fronts.base.Frontend` which was
                  previously saved with the given name.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Load front end instance that was saved.

                  Sub-classes generally do not need to implement this
                  method. They can implement get_read_stream instead.

        """
        if only_hdr and front_cls is None:   # If only_hdr we can juse assume
            front_cls = front_base.Frontend  # generic Frontend for now.
        if front_cls is None:
            if allow_load or (allow_load is None and self.allow_load):
                hdr = self.load(uid, only_hdr=True)
                mod = importlib.import_module(hdr['mod_name'])
                front_cls = getattr(mod, hdr['cls_name'])
        stream = self.get_read_stream(uid)
        result = front_cls.deserialize(stream, self, only_hdr=only_hdr)
        return result

    def get_read_stream(self, uid):
        """Return a file-like object to read serialized representation of name.

        :param uid:    Either a string name or a Frontend instance or some
                       other unique id that the backend supports for loading
                       an item.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   A file-like object with a read method.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Sub-classes can implement this method in order to allow
                   load to work.

        """
        raise NotImplementedError

    def write_serialized(self, front, serialized):
        """Write a serialized representation of front to this backend.

        :param front:    Instance of the thing we are serializing.

        :param serialized:  The serialized representation of front.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Sub-classes shall implement this method to write the
                   data to the backend.

        """
        raise NotImplementedError

    def delete(self, uid):
        """Delete the object with the given uid if present.

        :param uid:    Either a string name or a Frontend instance or some
                       other unique id that the backend supports for loading
                       an item.

        It is considered undefined to delete an object if it does not exist.
        Sub-classes can either raise KeyError or do nothing in such cases.
        This is because different backends may have different performance
        costs for verifying if an object exists before deleting it.
        """
        raise NotImplementedError
