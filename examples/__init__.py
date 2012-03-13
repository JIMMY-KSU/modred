# This file makes the modred directory a python package.

# Modules to load when using "from modred import *"
#__all__ = ['bpod', 'bpodltirom', 'dmd', 'era', 'fieldoperations',
#		'okid', 'parallel', 'pod', 'reductions', 'util']

# Modules whose internal contents are available through the 
# modred namespace as "modred.foo()" are imported below.
# For example, this allows "myPOD = modred.POD()" rather than
# "myPOD = modred.POD.POD()".
# Since we have a small library with few classes and functions,
# it's easiest to make many modules available from the top level.
# There are no naming conflicts and there is no room for confusion.

from simpleuse import *

