"""shiptoasting.tech.ccp.is flask frontend.

For when you really need to give a toast to a ship in Eve Online.
"""


import io
import os
import re
from setuptools import setup
from setuptools import find_packages


def find_version(filename):
    """Uses re to pull out the assigned value to __version__ in filename."""

    with io.open(filename, "r", encoding="utf-8") as version_file:
        version_match = re.search(r'^__version__ = [\'"]([^\'"]*)[\'"]',
                                  version_file.read(), re.M)
    if version_match:
        return version_match.group(1)
    return "0.0.0"


if os.path.isfile("README.md"):
    with io.open("README.md", encoding="utf-8") as opendescr:
        long_description = opendescr.read()
else:
    long_description = __doc__


with io.open("requirements.txt", encoding="utf-8") as openreqs:
    REQUIRES = openreqs.read().splitlines()


setup(
    name="shiptoasting",
    version=find_version("shiptoasting/__init__.py"),
    description="shiptoasting.tech.ccp.is flask frontend.",
    author="Adam Talsma",
    author_email="se-adam.talsma@ccpgames.com",
    url="https://shiptoasting.tech.ccp.is/",
    entry_points={
        "paste.app_factory": ["main = shiptoasting.web:production"],
        "console_scripts": ["shiptoasting-dev = shiptoasting.web:development"],
    },
    install_requires=REQUIRES,
    extras_require={"deploy": ["gunicorn"]},
    include_package_data=True,
    zip_safe=False,
    package_data={
        "shiptoasting": [
            os.path.join("shiptoasting", "templates", f) for f in
            os.listdir(os.path.join("shiptoasting", "templates"))
        ]
    },
    packages=find_packages(),
    long_description=long_description,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Flask",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2.7",
    ],
)
