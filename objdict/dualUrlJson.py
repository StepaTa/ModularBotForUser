#
from __future__ import (absolute_import, division,
                        print_function) #, unicode_literals)
import decimal
try:
    import urllib.parse as urlparselib
except ImportError: #above is python 3
    import urllib as urlparselib
try:
    unicode
except NameError: #no word 'unicode' in python 3
    unicode=str
class DummyClass:
    pass
try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId=DummyClass

import json

import os
import datetime
from collections import OrderedDict

from .objDict import ObjDict
from . import objDict

urldecode = urlparselib.unquote

safesplit = lambda x, y: len(x.split(y, 1)) == 2 and \
        x.split(y, 1) or [x.split(y)[0], ""]

noControls = lambda text: ''.join([a for a in text if ord(a) >= ord(' ')])

try:
    from fatalError import FatalError
    guiError=True
except (ImportError,SyntaxError):
    guiError=False


def arrayUrlDecode(theArray):
    return [urldecode(s) for s in theArray]


def urlParse(string,splitDash=None):
    ''' values for 'split dash' are
                None:only split if dash at field end
                True:always split dash
                False: Never
    '''
    res = OrderedDict()
    equates = noControls(string).split("&")
    #//array_walk($equates,"dumpit");
    # i= 0;
    for equate in equates:
        pair = equate.split("=")  # ,$equate)
        if len(pair) == 2:
            if len(pair[0]) > 0:
                splits = pair[1].split("-")
                splitThis=splitDash
                if splitDash is None and pair[1][-1:] == '-':
                    splitThis= True
                if len(splits) > 1 and splitThis:
                    if pair[1][-1:] == "-":
                        splits = splits[:-1]  # take of last where trailing-
                    res[pair[0]] = arrayUrlDecode(splits)
                    # debecho('arrayurldec',pair,splits,arrayUrlDecode(splits))
                else:
                    res[pair[0]] = urldecode(pair[1])
    return res
#phpparse=urlParse #deprecate use of this name

def phpparseAll(strng, level="0",splitDash=None):
    ''' parse multi levels with 'sectX=' sections
            each section creates own dictionary
                this 'sect' functionality to be deprecated as 'post' takes over

                values for 'split dash' are passed to urlParse
    '''
    tmp = strng.split("sect%s=" % level)
    res = OrderedDict()  # debecho('tmp',tmp)
    if len(tmp[0]) > 1:
        res = urlParse(tmp[0],splitDash)
    for tmpi in tmp[1:]:  # ($i=1;$i < sizeof($tmp);$i++)
        secHdr, secBody = safesplit(tmpi, "&")
        secLbl, secKey = safesplit(secHdr, "-")
        #debecho("sect lbl,key,body",secLbl,secKey,secBody)
        if secKey == '':
            res[secLbl] = urlParse(secBody,splitDash) #  tmpi[seclen:])#(substr(tmpi,$seclen));
        else:
            sub = secBody.split(secKey + "=")  # ,substr(tmpi,$seclen));
            #subres="";
            subres = urlParse(sub[0])  # ;//sub0 may be empty string!
            for subj in sub[1:]:  # ($j=1;$j<sizeof($sub);$j++)
                lbl, body = safesplit(subj, "&")
                subres[lbl] = urlParse(body,splitDash)
            res[secLbl] = subres
    #debecho('res',res)
    return res

"""def parse(string,mode=16):
    res={}
    equates= string.split('&');
    for equate in equates:
        pair= equate.split('=')
        if len(pair) == 2:
            if len(pair[0])>0:
                res[pair[0]] = pair[1]
    if mode==8:
        return unUnicode(res)
    else:
        return res"""
#


def ordUnUnicode(value):
    """ this is completely a python2 thing and should be able to just
    return value in python 3"""

    def chkNum(rawval):
        val = str(rawval)
        if val.isdigit():
            val = int(val)
        else:
            try:
                val = float(val)
            except ValueError:
                val = str(val)
        return val

    #if isinstance(value, OrderedDict)or isinstance(value, dict):
    if type(value) in (OrderedDict, dict):
        newobj = OrderedDict()
        for key, value in value.items():
            #print ('doing dict',key)
            key = ordUnUnicode(key)
            newobj[key] = ordUnUnicode(value)
    elif isinstance(value, list):
        newobj = []
        for i in value:
            #print ('in i loop',i,' ck:',ordUnUnicode(i), ' val:', value,)
            newobj.append(ordUnUnicode(i))
        #print ('newobh now', newobj)
    elif isinstance(value, unicode):
        newobj = str(value)  # chkNum(value)
    else:
        newobj = value

    return newobj


def jsParse(strng,DefaultType=ObjDict):
    #res = json.loads(strng, object_pairs_hook=OrderedDict
    #     ,parse_float=decimal.Decimal)
    if False: #no__type__:
        res = json.loads(strng  , object_pairs_hook=OrderedDict
         ,parse_float=decimal.Decimal)
    else:
        res = objDict.loads(strng  ,object_pairs_hook=ObjDict,
         DefaultType=DefaultType, parse_float=decimal.Decimal)
    return res #ordUnUnicode(res)


def combiParse(strng,getParms=True,errors=True
        ,splitDash=None,no__type__=None,DefaultType=ObjDict):
    """combiParse takse a string either encoded in the old extended get format
        or json or even a mix and returns an ordered dict with Decimals
        set 'getParms' to false to only parse json- or call jsParse anyway
        if 'errors' return valueerror if cannot parse

        splitDash passed to phpparseAll

        Set DefaultType to 'None' to raise errors for __type__ dicts
        where no matching class is found
    """
    if no__type__ is False:
        DefaultType=None
    elif no__type__ is None:
        no__type__=False

    erlist= () if errors else (ValueError)
    if '=' in strng and getParms:
    #consider making about "if not '{' in strng"  to bias towards json
    #in unparse could ensure escaping '{' characters
        if '\n' in strng:
            res= [phpparseAll(part,splitDash=splitDash)
                  for part in strng.split('\n') if part.strip() ]
        else:
            res = phpparseAll(strng,splitDash=splitDash)
        if 'json' in res:
            res.merge(jsParse(res['json']),DefaultType=DefaultType)
    elif strng.strip():
        try:
            res = jsParse(strng,DefaultType)
        except erlist as err:
            res= OrderedDict()
    else: # case nothing to parse
        return OrderedDict()
    return res


def objWalk(value, xpand=None, depth=0):
    indent = '.' * 4 * depth
    if isinstance(value, OrderedDict)or isinstance(value, dict):
        reslist = []
        joins = ', '
        if depth < 3:
            joins += '\n' + ('.' * 4 * depth)
        for key, value in value.items():
            reslist.append(str(key) + ':'
                + objWalk(value, xpand, depth + 1))
        return '{ ' + joins.join(reslist) + indent + '}\n'
    elif isinstance(value, list):
        reslist = []
        joins = ', '
        for i in value:
            reslist.append(objWalk(i, xpand, depth + 1))
        return ' [ ' + joins.join(reslist) + ' ]'
        #print ('newobh now',newobj)
    elif isinstance(value, unicode):
        res = str(value)  # chkNum(value)
    else:
        res = str(value)

    return res


def safeString(strng):
    """
    this ensures strings are safe in parse strings
    """
    res = urlparselib.quote(strng)
    if res[-1:]== '-':
        res= res[:-1]+'%2d'
    return res

    return res
def unURL(indict,depth=0):
    def dictToUrl(thedict,depth=0,excludes=[]):
        def unUrlItem(k,v):
            if isinstance(v,(int,float,decimal.Decimal)): #could move floats to use e
                return "{}={}&".format(k,v)
            elif isinstance(v,str):
                return "{}={}&".format(k,safeString(v))
            elif isinstance(v,(list,tuple))and v:#no empty lists
               # should check type of elements in v
                return "%s=%s-&"% (k,'-'.join(v))
            print('unhandled unurlitem',type(v),v,)
            return ''

        if not isinstance(thedict,dict):
            print('te',type(thedict),thedict)
            return ''
        res=''
        for k,v in thedict.items():
            if k not in excludes:
                if isinstance(v,(dict,OrderedDict)):
                    strng=[]
                    res+='sect{0}={1}-zzz{0}&'.format(depth,k)
                    #print('inside',v)
                    for n,item in v.items():
                        #print('at n: ',n,type(item))
                        if isinstance(item,(dict)):
                            res+='zzz{}={}&{}'.format(depth,n, dictToUrl(item,depth+1,['dfull']))
                        else:
                            res+=unUrlItem(n,item)

                else:
                    res+=unUrlItem(k,v)

        return res
    if not isinstance(indict,(dict,OrderedDict)):
        raise ValueError('unURl of not dict: '+repr(indict))
    res=dictToUrl(indict)
    return res
    strngs=[]
    for key,value in indict.items():

        strng=''
        strng+=dicttoUrl(key,['itemList'])+'sect0=items-zzz&'
        for n,item in enumerate(item['itemList']):
            strng+='zzz=%s&%s'%(n+1, dicttoUrl(item,['dfull']))
        strngs.append(strng)
    debecho('valueToStr',strngs)
    #stopit()
    return '\n'.join(strngs)


def unParse(obj, url=False,skip={},include={} , **nparms):
    """unParse serialises obj - putting in URL format if url= true
        url case has data limitations compared to json
        and escaping '=' characters otherwise to elimate confusions with urls
        passing 'indent'' (e.g indent = 4) formats the output but can be read
        skip and include at dictionaries or items of types to include or skip
        allObjs=True  will return 'str(obj) for any object that
                    raises a type error tyring to unParse.
                    Beware is unexpect str for obj
    """

    ObjectEncoder = objDict.ObjectEncoderAll if nparms.pop(
                            'allObj',False) else objDict.ObjectEncoderStd

    if url:
        return unURL(obj)
        #return urllib.urlencode(obj)
    else:
        #res = json.dumps(obj, cls=ObjectEncoder, **nparms)
        res = objDict.dumps(obj, cls=ObjectEncoder, **nparms)
        return res.replace('=', '\\u003D')


def reKey(theDict, key, theType=None, saveKey=None):
    """ take dict of dict - and make one of the fields the new key for
    the top level dict, save the old key if saveKey"""
    res = OrderedDict()
    for k, v in theDict.iteritems():
        if saveKey:
            v[saveKey] = k
        res[v[key]] = v if not theType else theType(v)
    return res


def toList(theDict, key, theType=None):
    """convert dict fo dicts to list dicts- add key into dict in list
    and cast each item of list as 'theType'  """
    def retype(k, v, key, theType):
        if key:
            v[key] = k
        return v if not theType else theType(v)
    return [retype(k, v, key, theType) for k, v in theDict.iteritems()]


# the testing code
if __name__ == '__main__':
    indebug = True

    class PageEmulator(object):
        def write(self, pstr):
            print (pstr.replace('<br>', '\n'))

    class Fred:
        def __init__(self,a,b):
            self.a=a
            self.b=b

    @encode.to_object()
    @decode.from_object()
    class DataModel(object):
        def __init__(self, id=0, value=7,**kwargs):
            self.id = id
            self.value = value
        def __repr__(self):
            return '<DM id:{id} val:{value}>'.format(**self.__dict__)
    foo=DataModel(1,'silly')
    data = {'a':5.6,'b':DataModel(5, foo)}
    print('dat',data['b'])
    dumdat=encode.dumper(data)
    print('dumper',dumdat)
    d2=decode.loader(dumdat)
    print('load',d2)


    #splitDash tests
    b="a=123&b=456-789&d=abc-def"
    a=combiParse(b,splitDash=True)
    print(a)
    rawdata=unParse({'a':5.6,'b':{'c':1}
                ,'c':DataModel(5, foo)})
    data=combiParse(rawdata)
    print('rawdat',rawdata,data)
    print ('data\n',unParse(data,indent=4))

    theReq = PageEmulator()

    try:
        with open('parse.txt') as parseFile:
            testmsg = parseFile.read()
    except IOError:
        print ("file parse.txt not found, using internal test\n")
        testmsg = ("tt=os&stb=8061&pn=61411541240&"
              "txnref=3181&jnr=1-01e9b7d74bd9bde1&"
            "appver=1.1.15&delMode=3&pick=0&sp=3.0193632410-&"
            "sect0=ord-isq&isq=0&ico=cCappucino&n=1&sz=0&fl=0"
            "&add=&req=&price=300&du=1")
    #print ("input text to parse")
    a = combiParse(testmsg)
    print ('a is', a, "\n\n  objwalks\n", objWalk(a), \
     '\n\njson \n', unParse(a, indent=4))

    #import urllib
    ur=unParse(a)
    #print ('json', ur, '\nurl', urlparselib.urlencode({'json':ur}))

    b=combiParse('{"rc": "0", "stn": "Ju\u003Dra at Rozelle1", "fav": "", "stf": "tDUEN", "stb": "8061", "tag": "wap"} ')


    print ('\n uparse b', unParse(b))

    #necho(a)
