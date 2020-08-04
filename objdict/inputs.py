#
def inputs(prompt, cls=str, default='', file=None):
    res = True
    while res:
        res = input(prompt)
        if res:
            try:
                yield cls(res)
            except ():
                yield default
