from Cython.Build import cythonize
from setuptools.extension import Extension
from setuptools import setup

extensions = Extension('clara.py.pylpsolve', ['clara/pylpsolve.pyx'],
                       libraries=['lpsolve55'])

setup(
    name='MyProject',
    ext_modules=cythonize(extensions),
)
