#
from objdict import dumps
from enum import Enum
class OEnum(Enum):

    def __json__(self, internal=False, *args):
        tmp = {'__type__':self.__class__.__name__, 'name': self.name}
        if internal:
            return tmp
        return dumps(tmp) #elf.__dict__)

    @classmethod
    def __from_json__(cls, data):
        """ decodes from n or v"""
        ddata = dict(data)
        if 'name' in ddata:
            return cls[ddata['name']]
        elif 'value' in ddata:
            return cls(ddata['value'])
        else:
            raise TypeError("Missing name")
