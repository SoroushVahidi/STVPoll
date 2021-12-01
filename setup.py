import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.rst')) as f:
    CHANGES = f.read()

requires = (
    'tarjan',
)

tests_require = (
)

setup(
    name='STVPoll',
    version='0.3.0',
    description='STV polling methods',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    ],
    author='Johan Schiff & Betahaus development team',
    author_email='johan@betahaus.net',
    url='https://github.com/VoteIT/STVPoll',
    keywords='election poll stv',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    extras_require={
        'testing': tests_require,
    },
    install_requires=requires,
)
