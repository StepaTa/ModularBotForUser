#
from objdict import dumps, from_json
from collections import namedtuple, OrderedDict

KeyObj = namedtuple("KeyObj", "type default")

def keyObj(kstr):
    """decodes a 'key' into name,(<type>,<default>)
    eval() is needed before using type or default
    """
    split1 = kstr.split(":")
    split2 = (split1[1:] or["None"])[0].split("=")
    return split1[0],KeyObj(split2[0],(split2[1:] or[None])[0])

@from_json()
class Struct(object):
    """Struct class uses __keys__ to build an __init__ method
    current syntax allows for :type and =default in keys,
    but is not yet using these values
    """
    def __init__(self, *args, **kwargs):
        keystxt = kwargs.get('__keys__', getattr(self,'__keys__', '*'))
        if isinstance(keystxt, OrderedDict):
            #import pdb; pdb.set_trace()
            keys = keystxt
        else:
            keys = OrderedDict([keyObj(x) for x in keystxt.split()])
            keys.aster = '*' in  keys
            if keys.aster:
                del keys['*']
            self.__class__.__keys__ = keys

        if len(args)> len(keys):
            raise TypeError("{} has maxium {} list arguments".format(
                    self.__class__.__name__, len(args))
                )
        for key, val in zip(keys, args):
            setattr(self, key, val)
        shortage = len(keys) - len(args)
        if shortage:
            for key in list(keys.keys())[-shortage:]:
                if key not in kwargs:
                    if keys[key].default is None:
                        raise TypeError("{} has missing arg {} ".format(
                            self.__class__.__name__, key)
                                       )
                    else:
                        setattr(self, key, eval(keys[key].default))

        for key, val in kwargs.items():
            if not keys.aster and not key in keys:
                raise TypeError("{} has no {} argument".format(
                    self.__class__.__name__, len(keys))
                               )
            setattr(self, key, val)

    def __repr__(self):
        return self.__class__.__name__ + dumps(self.__dict__)
    def __str__(self):
        return dumps(self.__dict__)

    def __json__(self, data=None, internal=False):
        """ json can be used by derived classes....
        def __json__(self, **kwargs):
            return super().__json__( <mydict>, **kwargs)
        """
        tmp = {'__type__':self.__class__.__name__}
        if data:
            tmp.update(data)
        else:
            tmp.update({k:v for k, v in self.__dict__.items() if k[0]!= '_'})

        if internal:
            return tmp
        return dumps(tmp) #elf.__dict__)

    def __eq__(self, other, report=False):
        """ tests that all fields in 'other' are also in self, and have same value
        this allows 'self' to have additional fields, just checks equality of fields
        in other!
        Normal usage involves instancing a comparison struct with the fields
        needing to be compared.
        If 'report' than an error is raise explaining diff
        """
        if not isinstance(other, Struct):
            if report:
                tname = other.__class__.__name__
                raise TypeError('cannot compare {} to Struct'.format(tname))
            return False
        keys = other.__dict__.keys()

        for key in keys:
            if getattr(self, key, None) != getattr(other, key):
                if report:
                    raise ValueError("struct not eq at " + key)
                return False
        return True

    # def __inter__(self):
    #     print("this is just a test")
    def items(self):
        return [(k,v) for k, v in self.__dict__.items() if k[0]!= '_']

class DictStruct(Struct):
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)
