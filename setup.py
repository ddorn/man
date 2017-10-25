# THIS FILE IS AUTOMATICALLY GENERATED. IT IS POINTLESS TO MODIFY IT

from setuptools import setup

try:
    with open('readme.rst') as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = 'Project manager for pypi libraries' 

setup(
    name='man',
    version='1.4.0',
    packages=['man'],
    url='https://github.com/ddorn/man',
    license='MIT',
    author='Diego Dorn',
    author_email='diego.dorn@free.fr',
    description='Project manager for pypi libraries',
    long_description=long_description,
    install_requires=['pyconfiglib==1.*', 'pypandoc', 'superprompt'],
    include_package_data=True,
    scripts=dict(console_scripts=['man=man.man:man'])
)
