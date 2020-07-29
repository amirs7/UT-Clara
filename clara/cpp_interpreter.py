from .c_interpreter import CInterpreter
from .interpreter import addlanginter


class CppInterpreter(CInterpreter):
    pass


addlanginter('cpp', CppInterpreter)
