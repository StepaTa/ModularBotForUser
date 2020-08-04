from collections import namedtuple
import datetime
YMD=namedtuple('YMD','y m d')
months={'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}

      
def strToDate(val):
    '''turns  a string into a date'''
    swap=False
    for char in ':/- ':
        if char in val:
            swap=True
            #print('f',char,val)
            res=YMD(*val.split(char))
            break
    else:
        #no separator found assum ddmmyy
        if len(val) == 4: #expiry date?
            res=YMD('20'+val[2:], val[:2], 1)
        elif len(val) == 6:
            res=YMD('20'+val[4:], val[2:4], val[:2])
        elif len(val)==8:
            res=YMD(val[4:], val[2:4], val[:2])
        else:
            raise ValueError('Cannot convert str to date: no separator found and bad length')
    if res.m in months:
        month = months[res.m]
        res = YMD(res.y, month, res.d)
    elif res.y in months:
        month = months[res.y]
        res = YMD(res.d,month,res.m)
        swap = False
    try:
        res= YMD(*(int(a) for a in res))
    except ValueError:
        raise ValueError('date with non integer part')
    if swap and (res.y <32):
        res = YMD(res.d,res.m,res.y)
    return datetime.date(*res)

for text in inputs('enter date'):
    try:
        print('Date: {}'.format(strToDate(text.lower())))
    except ValueError as e:
        print('had an error: ',e)
