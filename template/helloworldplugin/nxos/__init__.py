try:
    __import__('abstract').declare_token(__name__)
except Exception as e:
    import warnings
    warnings.warn('Could not declare abstraction token: ' + str(e))

from .plugin import *