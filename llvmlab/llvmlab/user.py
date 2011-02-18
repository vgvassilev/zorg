"""
LLVM-Lab User Objects
"""

from llvmlab import util

class User(util.simple_repr_mixin):
    @staticmethod
    def fromdata(data):
        version = data['version']
        if version != 0:
            raise ValueError, "Unknown version"

        return User(data['id'], data['passhash'],
                    data['name'], data['email'])

    def todata(self):
        return { 'version' : 0,
                 'id' : self.id,
                 'passhash' : self.passhash,
                 'name' : self.name,
                 'email' : self.email }

    def __init__(self, id, passhash, name, email):
        self.id = id
        self.passhash = passhash
        self.name = name
        self.email = email
