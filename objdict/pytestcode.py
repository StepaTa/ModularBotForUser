
"""
this is an automator to run pytest.

"""

json_layout = """  file: pytester.json required.
{ "app": <path to application folder within project "."?>,
  "path": <pythonpath from 'app' to folder to find project libs(".")>
  "tests": <path to tests within project (used for xtra json testlists)>",
  "options" : {
      <optname>:{"help":<help text>, "opt":<option>},
      ....  repeat for each option
           }
}"""
import sys
try:
    import pytest
except ImportError:
    pytest = None
import os

from objdict import ObjDict, JsonDecodeError

def printhelp(parms):
    if not 'options' in parms or not parms.options:
        print("No options available, edit pytester.json")
    else:
        print("\n options are:-")
        for key, optn in parms.options.items():
            print("{}: {}".format(key, optn.help))

def pytester(argv, config="pytester.json"):
    """main function does all the work"""

    print("python", sys.version)
    if pytest is None:
        print('Install pytest to use pytester')
        return

    try:
        with open(config) as f:
            txt = f.read()
    except FileNotFoundError:
        print(json_layout)
        return None

    if not txt:
        print("file empty?")
    else:
        try:
            parms = ObjDict(txt)
        except JsonDecodeError:
            print("oops" + txt)

    # first save base folder
    base_folder = os.path.abspath('.')
    # neow read from  read sup app files
    testdir = parms.get('tests')
    try:
        test_folder_list = os.listdir(testdir)
    except FileNotFoundError:
        test_folder_list = []

    extras = [os.path.join(testdir, fn) for fn in test_folder_list if fn[-5:] == '.json']

    for extra in extras:
        with open(extra) as f:
            try:
                xopts = ObjDict(f.read())
            except JsonDecodeError:
                print('bad json format: ', extra)
            else:
                parms.options.update(xopts)

    #for file in os.path()
    #sys.path.append('.')

    cdir = os.listdir()
    if  "app" in parms and parms.app in cdir:
        print('chdir')
        os.chdir(parms.app)

    if "path" in parms:
        sys.path = [os.path.abspath(p) for p in parms.path.split(',')] + sys.path[1:]
        #print('pyp: ', sys.path)
    #print(os.listdir('.'))


    testargs = [] #['pytest']
    #if debuging
    testargs += ['--pdb', '--maxfail=1']
    #now the test_pages

    if len(argv) > 1:
        a1 = argv[1]
        if 'options' in parms and a1 in parms.options:
            test = parms.options[a1].opt 
            #'./tests/test_ObjDict.py::TestInstance__json__::test_dict_subobj_to_json'
            testargs.append(test)
        else:
            printhelp(parms)
            return

    try:
        pytest.main(testargs)
    except BaseException as ex:
        import pdb; pdb.set_trace()
        print('Pytest returned:', ex)

