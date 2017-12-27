"""This module provides various simple implementations of backends.
"""


import os
import tempfile

from oxtie.backs import base as back_base


class FileBackend(back_base.Backend):
    """File based backend.

    As described in __init__, you just need to provide a string `root`
    indicating the root directory. Then files will be stored inside
    that directory.

    """

    def __init__(self, root=None, *args, **kwargs):
        """Initializer.

        :param root=None:  String indicating root directory to save in.

        :param *args, **kwargs:  Passed to parent __init__. See docs
                                 for base.Backend class for details.

        """
        super().__init__(*args, **kwargs)
        self.root = root

    def write_serialized(self, front, serialized):
        """Implement as required by parent to write to file.
        """
        path = os.path.join(self.root, self.prep_key(front))
        open(path, 'wb').write(serialized)

    def get_read_stream(self, uid):
        """Implement as required by parent to read from file.
        """
        path = os.path.join(self.root, self.prep_key(uid))
        stream = open(path, 'rb')
        return stream

    def prep_key(self, uid):
        """Prepare and return data key (i.e., file path) from uid.

        The uid can either be a Frontend instance or result of calling
        get_key on a Frontend instance.
        """
        dummy = self  # to suppress pylint messages
        if not isinstance(uid, dict):
            uid = uid.get_key()
        keypath = '.'.join(['%s=%s' % (n, uid[n]) for n in sorted(uid)])

        return keypath

    def delete(self, uid):
        path = os.path.join(self.root, self.prep_key(uid))
        os.remove(path)


class TempFileBackend(FileBackend):
    """Simple file backend which will put files in the default temp directory.
    """

    def __init__(self, root=None, *args, **kwargs):
        """Initializer.

        :param root=None:   Optional root directory for file backend.

        :param *args, **kwargs:   As for FileBackend.__init__.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Like FileBackend but if root is None, we use
                  the file systems temporary directory as the backend.

        """
        if root is None:
            root = tempfile.gettempdir()
        super().__init__(root, *args, **kwargs)
