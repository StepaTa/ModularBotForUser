#
from __future__ import (absolute_import, division,
                        print_function) #, unicode_literals)
import decimal
from collections import namedtuple

try:
    import urllib.parse as urlparselib
except ImportError: #above is python 3
    import urllib as urlparselib
try:
    unicode
except NameError: #no word 'unicode' in python 3
    unicode = str
class DummyClass:
    pass
try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = DummyClass

import inspect
import json
#from jsonweb import encode #,decode

import os
import datetime
from collections import OrderedDict

import sys
import types
PY3k = sys.version_info[0] == 3

if PY3k:
    basestring = (str, bytes)
    _iteritems = "items"
else:
    basestring = basestring
    _iteritems = "iteritems"

def items(d):  #this is to become deprecated!
    return getattr(d, _iteritems)()


class ObjDictError(Exception):
    def __init__(self, message, **extras):
        super(Exception, self).__init__(self, message)
        self.extras = extras

class JsonDecodeError(ObjDictError):
    """
    Raised when python containers (dicts and lists) cannot be decoded into
    complex types. These exceptions are raised from within an ObjectHook
    instance.
    """
    def __init__(self, message, **extras):
        ObjDictError.__init__(self, message, **extras)

class ObjectNotFoundError(JsonDecodeError):
    def __init__(self, obj_type):
        JsonDecodeError.__init__(
            self,
            "Cannot decode object {0}. No such object.".format(obj_type),
            obj_type=obj_type,
        )

#-----------------------------------------------------------
#  class registry
#-----------------------------------------------------------


class FakeFloat(float):

    def __init__(self, value):
        self._value = value

    def __repr__(self):
        return str(self._value)

from collections import namedtuple #can we used ObjDict instead? circular!
ClsEnc = namedtuple('ClsEnc', 'cls enc')

def type_str(obj):
    return '_'+obj.__class__.__name__ +':' +str(obj)

class ClassRegistry:
    """ The Encoder (for to json) table is in two parts.
    exact matches, and 'isinstance' matches.
    classes can have an encoder for the exact class,
    or for any class which matches an isinstance test,
    or separate encoders for both cases

    inst_table is a list of ClsEnc tuples
    exact_table is a dictionary of inst_tables where all classes in each 
    inst_table have the same name
    """

    def __init__(self):
        self.exact_table = {}
        self.inst_table = []
        self.add_to(decimal.Decimal, FakeFloat)
        self.add_to(datetime.datetime, str)
        self.add_to(datetime.date, str)
        self.add_to(datetime.timedelta, str)
        self.add_to(ObjectId, type_str)

    def add_to(self, cls, encoder, subclasses=False):

        if subclasses:
            lst = inst_table
        else:
            name = cls.__name__
            if not name in self.exact_table:
                self.exact_table[name] = []
            lst = self.exact_table[name]

        for entry in lst:
            if entry.cls == cls:
                entry.enc = encoder
                break
        else:
            lst.append(ClsEnc(cls=cls, enc=encoder))


    def find(self, cls):
        """ search exact match or isinstance match"""
        lst = self.exact_table.get(cls.__name__, [])
        for entry in lst:
            if entry.cls == cls:
                return entry

        for entry in self.inst_table:
            if isinstance(cls, entry.cls):
                return entry

        return None

    def do_method(self, entry, obj):
        return entry.enc(obj)


json_registry = ClassRegistry()
ClassEntry = namedtuple("ClassEntry", "cls handler")

class _ClassRegister(object):
    def __init__(self):
        self._classes = {}
        self._deferred_updates = {}

    def add_class(self, cls, handler, type_name=None):
        name = type_name or cls.__name__
        self._classes[name] = ClassEntry(cls, handler)

    def get(self, name):
        """
        Get a handler tuple. Return None if no such handler.
        """
        return self._classes.get(name)

    def set(self, name, handler_tuple):
        """
        Add a handler tuple (handler, cls, schema)
        """
        self._classes[name] = handler_tuple

    def clear(self):
        self._classes = {}
        self._deferred_updates = {}

    def update_handler(self, name, cls=None, handler=None, schema=None):
        """
        Modify cls, handler and schema for a decorated class.
        """
        handler_tuple = self._classes[name]
        self.set(name, self.__merge_tuples((handler, cls, schema),
                                           handler_tuple))

    def xupdate_handler_deferred(self, name, cls=None,
                                 handler=None, schema=None):
        """
        If an entry does not exist in _classes an entry will be added to
        __deferred_updates instead. Then when add_handler is finally called
        values will be updated accordingly. Items in __deferred_updates will
        take precedence over those passed into add_handler.
        """
        if name in self._classes:
            self.update_handler(name, cls, handler, schema)
            return
        d = self.__deferred_updates.get(name, (None,)*3)
        self.__deferred_updates[name] = self.__merge_tuples(
            (handler, cls, schema), d)

    def copy(self):
        handler_copy = _ClassRegister()
        [handler_copy.set(n, t) for n, t in self]
        return handler_copy

    def __merge_tuples(self, a_tuple, b_tuple):
        """
        "Merge" two tuples of the same length. a takes precedence over b.
        """
        if len(a_tuple) != len(b_tuple):
            raise ValueError("Iterators differ in length.")
        return tuple([(a or b) for a, b in zip(a_tuple, b_tuple)])

    def __contains__(self, handler_name):
        return handler_name in self._classes

    def __getitem__(self, handler):
        return self._classes[handler]

    def __iter__(self):
        for name, handler_tuple in self._classes.items():
            yield name, handler_tuple

_default_class_register = _ClassRegister()


#------------------------------------------------------------------------
# from json: loading
#------------------------------------------------------------------------

class ObjPairHook(object):
    """
    This class encapsulates the object decode mechanism used to create or
    recreate classes fom json text files.

    An instance of an ObjPairHook provides a decode_pairs() method.
    This method checks for a __type__ specified from the json data.
    If their is no __type__ then the 'BaseHook' object is used to instance
    an object from the Ojbect Pairs. The BaseHook can be a class or any other callable.
    If the BaseHook has a 'from_json' property then this 'from_json' method will
    be called, otherwise the BaseHook will be called directly.

    The 'DefaultType' is actually a default base class for the case where the
    __type__ is specified, but does not correspond to a class in the list of
    classes.
    Pairs hook uses two class lists.  The
    process the data, otherwise Hool does most of the work in managing the handlers that decode the
    json into python class instances. You should not need to use this class
    directly. :func:`make_pairs_hook` is responsible for instantiating and using it.
    """

    def __init__(self, classes_list=[], BaseHook=None,
                 BaseType=None):
        #self.classes = classes_list
        self.BaseHook = BaseHook
        self.DefaultType = BaseType
        handle_key = '__from_json__'

        if classes_list:
            _class_register = _default_class_register.copy()
            for cls in classes_list:
                name = cls.__name__
                if name in _class_register:
                    _class_register.update_class(name, **handler_dict)
                else:
                    _class_register.add_class(
                        each_class,
                        getattr(cls, handle_key, cls), name
                        )
        else:
            _class_register = _default_class_register

        self.classes = _class_register


    def from_json(self, obj):
        """
        This method is called for every dict decoded from a json string. The
        presence of the key ``__type__`` in ``obj`` will trigger a lookup in
        ``self.handlers``. If a handler is not found for ``__type__`` then an
        :exc:`ObjectNotFoundError` is raised. If a handler is found it will
        be called with ``obj`` as it only argument. If an :class:`ObjectSchema`
        was supplied for the class, ``obj`` will first be validated then passed
        to handler. The handler should return a new python instant of type ``__type__``.
        """
        if isinstance(obj, list):
            dobj = OrderedDict(obj)
            if "__type__" not in dobj:
                if self.BaseHook:
                    return self.BaseHook(obj)
                else:
                    #consider override if no baseHook to ObjDict
                    return dobj
            obj = dobj
        elif "__type__" not in obj:
            if self.BaseHook:
                # do factory with BaseHook entry?
                return self.BaseHook(obj)
            return obj
        #else:
        #    dobj=obj #should not apply with pairs hook
        obj_type = obj.pop("__type__") # does not do much!
        try:
            cls, factory = self.classes[obj_type]
        except KeyError:
            if self.DefaultType:
                #print("doing this type")
                #could do:  factory,cls,schema ...?
                ThisType = type(str(obj_type), (self.DefaultType, ),
                                {'_set_type':True})
                return ThisType(obj)
            raise ObjectNotFoundError(obj_type)

        try:
            #print("fact ret",cls)
            return factory(obj)
        except KeyError as e:
            raise ObjectAttributeError(obj_type, e.args[0])



#_default_object_handlers = _ObjectHandlers()

def make_kwargs(cls, args):
    return cls(**ObjDict(args))

def from_json(type_name=None, use=None):
    """
    Decorating a class with :func:`from_object` adds
    will allow :func:`json.loads`
    to return instances of that class, embeded within the object returned.

    The class can contain a 'from_json' class method that will receives
    a list of object pairs as a parameter, and return an instance of the class.

    This class method will normally perform any validation on the 'pairs' data
    (key, value list) that is decoded from json and provided as a paramter,
    extract the relevant data and pass that to the class init method.

    If no '__from_json__' class method is present, then handling depends
    on the the 'use' paramater.  If use is the defalt (None) the standard
    'make_kwargs' routine is used to init the class or if use is,
    True, the 'pairs' key/value
    list decoded from jsons will be provide as a parameter to the class init method
    The third alternative is to provide a custom method to decode from json::

        use=<custom_method>

    Here is an
    example using __from__json__ ::

        >>> from objdict import ObjDict, from_factoryobject, loader
        >>> @classmethod
        >>> def __from_json__(cls, pairlist):
        ...    obj = ObjDict(pairlist)
        ...    return cls( obj.first_name, obj.last_name )
        ...
        >>> @from_object()
        ... class Person(object):
        ...     def __init__(self, first_name, last_name):
        ...         self.first_name
        ...         self.last_name = last_name
        ...
        >>> person_json = '{"__type__": "Person", "first_name": "Shawn", "last_name": "Adams"}'
        >>> person = loader(person_json)
        >>> person
        <Person object at 0x1007d7550>
        >>> person.first_name
        'Shawn'

    The ``__type__`` key in the json text is very important.
    Without it the 'object_pairs_hook'
    will simply treat the data as a generic ObjDict object/dictionary.

    By default
    :func:`ObjPairHook.decode` assumes ``__type__`` will be the class's ``__name__``
    attribute. You can specify your own value by setting the ``type_name``
    keyword argument ::

        @from_object( type_name="PersonObject")

    Which means the json string would need to be modified to look like this::

        '{"__type__": "PersonObject", "first_name": "Shawn", "last_name": "Adams"}'
    """
    handle_key='__from_json__'

    def wrapper(cls):
        wrap_use = getattr(cls, handle_key, use)
        if wrap_use == True:
            wrap_use = cls
        elif wrap_use == None:
            def wrapkwargs(cls):
                def callkwargs(args):
                    return make_kwargs(cls, args)
                return callkwargs
            wrap_use = wrapkwargs(cls)

        _default_class_register.add_class(
            cls, wrap_use, type_name
        )
        return cls
    return wrapper


def make_pairs_hook(classes=None, BaseHook=None, DefaultBase=None):
    """
    Wrapper to generate :class:`ObjectHook`. Calling this function will configure
    an instance of :class:`ObjectHook` and return a callable suitable for
    passing to :func:`json.loads` as ``object_pairs_hook``.

    Dictionaries/objects without a  ``__type__``
    key are encoded as ObjDict objects ::

        >>> json_str = '{"obj":{"inside": "value"}}'
        >>> loader(json_str)
        {"obj":obnj dict
        >>> # lists work too
        >>> json_str = '''[
        ...     {"first_name": "bob", "last_name": "smith"},
        ...     {"first_name": "jane", "last_name": "smith"}
        ... ]'''
        >>> loader(json_str, as_type="Person")
        [<Person object at 0x1007d7550>, <Person object at 0x1007d7434>]

    .. note::

        Assumes every object a ``__type__``  kw is ObjDict

        ``handlers`` is an ObjDict with this format::

        {"Person": {"cls": Person, "handler": person_decoder, "schema": PersonSchema)}

    If you do not wish to decorate your classes with :func:`from_json` you
    can specify the same parameters via the ``classes`` keyword argument.
    Here is an example::

        >>> class Person(object):
        ...    def __init__(self, first_name, last_name):
        ...        self.first_name = first_name
        ...        self.last_name = last_name
        ...
        >>> def person_decoder(cls, obj):
        ...    return cls(obj["first_name"], obj["last_name"])

        >>> handlers = {"Person": {"cls": Person, "handler": person_decoder}}
        >>> person = loader(json_str, handlers=handlers)
        >>> # Or invoking the object_hook interface ourselves
        >>> person = json.loads(json_str, object_pairs_hook=make_pairs_hook(handlers))

    .. note::

        If you decorate a class with :func:`from_json` you can specify
        a list of classes to use
        """

    return ObjPairHook(classes, BaseHook, DefaultBase).from_json


def loads(json_str, **kw):
    """
    Call this function as you would call :func:`json.loads`. It wraps the
    :ref:`make_pairs_hook` interface and returns python class instances from JSON
    strings.

    :param ensure_type: Check that the resulting object is of type
        ``ensure_type``. Raise a ValidationError otherwise.
    :param handlers: is a dict of handlers. see :func:`make_pairs_hook`.
    :param as_type: explicitly specify the type of object the JSON
        represents. see :func:`make_pairs_hook`
    :param validate: Set to False to turn off validation (ie dont run the
        schemas) during this load operation. Defaults to True.
    :param kw: the rest of the kw args will be passed to the underlying
        :func:`json.loads` calls.


    """

    #object_pairs_hook=ObjDict,
    #    DefaultType=DefaultType, parse_float=decimal.Decimal

    baseword = "object_pairs_hook"

    #hookword= baseword if baseword in kw else "object_hook"
    kw[baseword] = make_pairs_hook(
        kw.pop("handlers", None),
        kw.pop(baseword, kw.pop("object_hook", ObjDict)),
        kw.pop("DefaultType", ObjDict)
    )

    #ensure_type = kw.pop("ensure_type", _as_type_context.top)

    #print("kw dict",kw)

    try:
        obj = json.loads(json_str, **kw)
    except ValueError as error:
        #import pdb; pdb.set_trace()
        print("error txt",error, error.args[0])
        raise JsonDecodeError(error.args[0])

    # if ensure_type:
    #     return EnsureType(ensure_type).validate(obj)
    return obj

##--------------------------------------------------------------------
##--------------------------------------- to json
##--------------------------------------------------------------------


class EncodeArgs:
    __type__ = None
    serialize_as = None
    handler = None
    suppress = None


def std__json__(self, enc=None, internal=False, **kw):
    """
    ---note self reference not updated obj is self!

    Handles encoding instance objects of classes decorated by
    :func:`to_json`. Returns a dict containing all the key/value pairs
    in ``obj.__dict__``. Excluding attributes that

    * start with an underscore.
    * were specified with the ``suppress`` keyword argument.

    The returned dict will be encoded into JSON.

    .. note::

        Override this method if you wish to change how ALL objects are
        encoded into JSON objects.

    """
    if not internal:
        return dumps(self, cls=ObjectEncoderAll, **kw)
    encode = self.__json__encode
    suppress = encode.suppress

    if enc and enc._exclude_nulls is not None:
        exclude_nulls = enc._exclude_nulls
    else:
        exclude_nulls = encode.exclude_nulls

    json_obj = {}

    def suppressed(key):
        return key in suppress or (enc and key in enc._hard_suppress)
    
    l1 = dir(self)
    if isinstance(self, dict):
        l2 = l1
        l1 = [i for i in self.keys()]
    for attr in l1:
        if attr == '__type__' or (
                not attr.startswith("_") and not suppressed(attr)):
            value = getattr(self, attr)
            if value is None and exclude_nulls:
                continue
            if not isinstance(value, types.MethodType):
                json_obj[attr] = value
    if not suppressed("__type__"):
        tname = self.__class__.__name__  # encode.__type__
        if tname not in ('ObjDict',):
            json_obj["__type__"] = tname
    return json_obj

def to_json(cls_type=None, suppress=None, handler=None, exclude_nulls=False):
    """
    Decorateor. To make your class instances JSON encodable decorate them with
    :func:`to_object`. The python built-in :py:func:`dir` is called on the
    class instance to retrieve key/value pairs that will make up the JSON
    object (*Minus any attributes that start with an underscore or any
    attributes that were specified via the* ``suppress`` *keyword argument*).

    Here is an example::

        >>> from jsonweb import to_object
        >>> @to_object()
        ... class Person(object):
        ...     def __init__(self, first_name, last_name):
        ...         self.first_name = first_name
        ...         self.last_name = last_name

        >>> person = Person("Shawn", "Adams")
        >>> dumper(person)
        '{"__type__": "Person", "first_name": "Shawn", "last_name": "Adams"}'

    A ``__type__`` key is automatically added to the JSON object. Its value
    should represent the object type being encoded. By default it is set to
    the value of the decorated class's ``__name__`` attribute. You can
    specify your own value with ``cls_type``::

        >>> from jsonweb import to_object
        >>> @to_object(cls_type="PersonObject")
        ... class Person(object):
        ...     def __init__(self, first_name, last_name):
        ...         self.first_name = first_name
        ...         self.last_name = last_name

        >>> person = Person("Shawn", "Adams")
        >>> dumper(person)
        '{"__type__": "PersonObject", "first_name": "Shawn", "last_name": "Adams"}'

    If you would like to leave some attributes out of the resulting JSON
    simply use the ``suppress`` kw argument to pass a list of attribute
    names::

        >>> from jsonweb import to_object
        >>> @to_object(suppress=["last_name"])
        ... class Person(object):
        ...     def __init__(self, first_name, last_name):
        ...         self.first_name = first_name
        ...         self.last_name = last_name

        >>> person = Person("Shawn", "Adams")
        >>> dumper(person)
        '{"__type__": "Person", "first_name": "Shawn"}'

    You can even suppress the ``__type__`` attribute ::

        @to_object(suppress=["last_name", "__type__"])
        ...

    Sometimes it's useful to suppress ``None`` values from your JSON output.
    Setting ``exclude_nulls`` to ``True`` will accomplish this ::

        >>> from jsonweb import to_object
        >>> @to_object(exclude_nulls=True)
        ... class Person(object):
        ...     def __init__(self, first_name, last_name):
        ...         self.first_name = first_name
        ...         self.last_name = last_name

        >>> person = Person("Shawn", None)
        >>> dumper(person)
        '{"__type__": "Person", "first_name": "Shawn"}'

    .. note::

        You can also pass most of these arguments to :func:`dumper`. They
        will take precedence over what you passed to :func:`to_object` and
        only effects that one call.

    If you need greater control over how your object is encoded you can
    specify a ``handler`` callable. It should accept one argument, which is
    the object to encode, and it should return a dict. This would override the
    default object handler :func:`JsonWebEncoder.object_handler`.

    Here is an example::

        >>> from jsonweb import to_object
        >>> def person_encoder(person):
        ...     return {"FirstName": person.first_name,
        ...         "LastName": person.last_name}
        ...
        >>> @to_object(handler=person_encoder)
        ... class Person(object):
        ...     def __init__(self, first_name, last_name):
        ...         self.guid = 12334
        ...         self.first_name = first_name
        ...         self.last_name = last_name

        >>> person = Person("Shawn", "Adams")
        >>> dumper(person)
        '{"FirstName": "Shawn", "LastName": "Adams"}'


    You can also use the alternate decorator syntax to accomplish this. See
    :func:`jsonweb.encode.handler`.

    """
    def wrapper(cls):
        if not hasattr(cls, '__json__'):
            cls.__json__ = std__json__
        encode = EncodeArgs()
        encode.serialize_as = "json_object"
        #cls._encode.handler = handler
        encode.suppress = suppress or []
        encode.exclude_nulls = exclude_nulls
        encode.__type__ = cls_type or cls.__name__
        cls.__json__encode = encode
        return cls #__inspect_for_handler(cls)
    return wrapper

#--------------------------------------------
# Encode + dumps
std_e_args = object()
#std_e_args.

class JsonEncoder(json.JSONEncoder):
    """
    This :class:`json.JSONEncoder` subclass is responsible for encoding
    instances of classes that have been decorated with :func:`to_json` or
    :func:`to_list`. Pass :class:`JsonWebEncoder` as the value for the
    ``cls`` keyword argument to :func:`json.dump` or :func:`json.dumps`.

    Example::

        json.dumps(obj_instance, cls=JsonWebEncoder)

    Using :func:`dumper` is a shortcut for the above call to
    :func:`json.dumps` ::

        dumper(obj_instance) #much nicer!


        object to be encoded should have:
            __json__encode property, which has encode arguments

    """

    _DT_FORMAT = "%Y-%m-%dT%H:%M:%S"
    _D_FORMAT = "%Y-%m-%d"

    def __init__(self, **kw):
        self._hard_suppress = kw.pop("suppress", [])
        self._exclude_nulls = kw.pop("exclude_nulls", None)
        self._handlers = kw.pop("handlers", {})
        if not isinstance(self._hard_suppress, list):
            self._hard_suppress = [self._hard_suppress]
        json.JSONEncoder.__init__(self, **kw)

    def default(self, o):
        # if o.__class__.__name__ not in ('DataModel','Decimal','date',
        #         'datetime','ObjectId'): #== 'RawClass':
        #     pass  # placeholder for debug
        if hasattr(o, '__json__'):
            e_args = getattr(o, "__json__encode", std_e_args)

            # Passed in handlers take precedence.
            if o.__class__ in self._handlers:  # was e_args.__type__ ...why (29/11/2016)
                assert False, "never gets here in test"
                return self._handlers[e_args.__type__](o)
            elif getattr(e_args, 'handler', None):
                assert False, "doesn't get here either"
                if e_args.handler_is_instance_method:
                    return getattr(o, e_args.handler)()
                return e_args.handler(o)
            elif getattr(e_args, 'serialize_as', 'json_object') == "json_object":
                #return self.object_handler(o)
                return o.__json__(internal=True)
            elif e_args.serialize_as == "json_list":
                return self.list_handler(o)

        # if isinstance(o, datetime.datetime):
        #     return o.strftime(self._DT_FORMAT)
        # if isinstance(o, datetime.date):
        #     return o.strftime(self._D_FORMAT)

        encoder = json_registry.find(o.__class__)
        if encoder:
            return json_registry.do_method(encoder, o)

        return json.JSONEncoder.default(self, o)

    def encode(self, o):
        #import pdb; pdb.set_trace()
        return super(JsonEncoder, self).encode(o)


def list_handler(self, obj):
    """
    Handles encoding instance objects of classes decorated by
    :func:`to_list`. Simply calls :class:`list` on ``obj``.

    .. note::

        Override this method if you wish to change how ALL objects are
        encoded into JSON lists.

    """
    return list(obj)

class ObjectEncoderStd(JsonEncoder):
    def encode(self, o):
        if isinstance(o, ObjDict):
            if o._set_type:
                o['__type__'] = o.__class__.__name__
        res = super(ObjectEncoderStd, self).encode(o)
        pass
        return res
        return super(ObjectEncoderStd, self).encode(o)
    def default(self, o):
        return super(ObjectEncoderStd, self).default(o)

#class ObjectEncoderAll(json.JSONEncoder):
class ObjectEncoderAll(ObjectEncoderStd): #JsonEncoder):
    def default(self, o):
        try:
            return super(ObjectEncoderAll, self).default(o)
        except TypeError as e:
            return str(o)



#----------------------------------------------
#------- ObjDict class
#----------------------------------------------

@to_json()
class Holder:
    def __init__(self,value,method):
        self.method = method
        self.value = value

    def __call__(self, *args, **kwargs):
        return self.method(*args, **kwargs)

    def __get__(self, obj, ibjtype):
        import pdb; pdb.set_trace()
        return self.value

    def __set__(self, obj, value):
        self.value = value

    def __json__(self, *args, **kwargs):
        return str(self.value)

@to_json() #note handled by dict encoder
@from_json()
class ObjDict(OrderedDict):
    _DICT_RESERVED =set(('items','keys','get','copy', 'dumps', 'from_json', 'fromkeys', 'get', 'items', 'keys',
        'loads', 'make_pairs_hook', 'move_to_end', 'pop', 'popitem', 'setdefault',
        'to_json', 'update', 'values','_DICT_RESERVED'))
    _DICT_RESERVED_NON_CALLS =set(('_DICT_RESERVED',))
    to_json = to_json
    from_json = from_json
    make_pairs_hook = make_pairs_hook
    JsonEncoder = ObjectEncoderAll
    loads=loads
    JsonDecodeError = JsonDecodeError

    #_set_type=False # can be overriden in instance
    def __init__(self,*args,**kwargs):
        set_type= kwargs.pop('_set_type',None)
        self._skipped_attrs = [] # data where key prevents being an attr
        self._seen_attrs= [] #reserved attributes already processed
        self.__keys__= kwargs.pop('__keys__', getattr(self,'__keys__',[]))
        self.__decimal__= kwargs.pop('__decimal__', getattr(self,'__decimal__',False))
 
        if isinstance(self.__keys__,str):
            self.__keys__=self.__keys__.split()
        predata=[]
        if len(args)==1 and isinstance(args[0],str):
            loadkw = {}
            if self.__decimal__:
                loadkw['parse_float'] = decimal.Decimal 
            predata=loads(args[0], **loadkw).items()
            args=[]
        elif self.__keys__ and len(args)== len(self.__keys__):
            predata=zip(self.__keys__,args)
            args=[]
        super(ObjDict,self).__init__(*args,**kwargs)
        if set_type is not None:
            self._set_type=set_type
        for arg in args:
            if isinstance(arg,dict):
                self.__dict__.update(**arg)

        # the following blocks would create duplication
        #self.__dict__.update(**kwargs)
        #self.update(**args)

        for key,data in predata:
            self[key]=data

        clnm = self.__class__.__name__ #set type for derived classes
        if clnm != 'ObjDict':
            self['__type__'] = clnm 
    @property
    def _set_type(self):
        return self.__dict__.get(
            '_set_type', self.__class__.__name__ != 'ObjDict')
    @_set_type.setter
    def _set_type(self,value):
        self.__dict__['_set_type'] = value #set inst value hiding property

    def __setitem__(self,key,value):

        super(ObjDict,self).__setitem__(key,value)
        if key in self._DICT_RESERVED and key not in self._seen_attrs:
            if False: #True: #isinstance(value,ObjDict) and key not in self._DICT_RESERVED_NON_CALLS:
                #this code waiting on OBJD-42
                call = getattr(super(ObjDict,self),key)
                setattr(self,key,Holder(value,call))

            else:
                self._skipped_attrs.append(key)
            self._seen_attrs.append(key)
        else:
            setattr(self,key,value)

    def __setattr__(self,attr,value):
        super(ObjDict,self).__setattr__(attr,value)
        if attr[:1] != '_':
            super(ObjDict,self).__setitem__(attr,value)


    # def __getitem__(self, key):
    #     if key == 'bms':
    #         import pdb; pdb.set_trace()
    #     return super(ObjDict,self).__getitem__(key)

    @classmethod
    def __from_json__(cls,thedict):
        """ same result as 'use=True' so makes this the default """
        #print('in handler',cls,thedict)
        return cls(thedict)

    def __str__(self):
        return self.__json__()

    def __repr__(self):
        return self.__class__.__name__ + ": " + self.__json__()

    def dumps(obj, **kw):
        """
        note: not called 'self' as can be used as unbound class method
        JSON encode your class instances by calling this function as you would
        call :func:`json.dumps`. ``kw`` args will be passed to the underlying
        json.dumps call.

        :param handlers: A dict of type name/handler callable to use.
         ie {"Person:" person_handler}

        :param cls: To override the given encoder. Should be a subclass
         of :class:`JsonWebEncoder`.

        :param suppress: A list of extra fields to suppress (as well as those
         suppressed by the class).

        :param exclude_nulls: Set True to suppress keys with null (None) values
         from the JSON output. Defaults to False.
        """
        return json.dumps(obj, cls=kw.pop("cls", ObjectEncoderAll), **kw)

dumps=ObjDict.dumps
