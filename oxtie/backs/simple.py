"""This module provides various simple implementations of backends.
"""

import os

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
        path = os.path.join(self.root, front.get_name())
        open(path, 'wb').write(serialized)

    def get_read_stream(self, uid):
        """Implement as required by parent to read from file.
        """
        path = os.path.join(self.root, self.prep_key(uid))
        stream = open(path, 'rb')
        return stream

    def prep_key(self, uid):
        """Prepare and return data key (i.e., file path) from uid.
        """
        dummy = self
        if isinstance(uid, str):
            return uid
        return uid.get_name()

    def delete(self, uid):
        path = os.path.join(self.root, self.prep_key(uid))
        os.remove(path)
