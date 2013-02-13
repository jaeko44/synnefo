# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.
#

import distribute_setup
distribute_setup.use_setuptools()

import os

from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))

from quotaholder_django.version import __version__

# Package info
VERSION = __version__
README = open(os.path.join(HERE, 'README')).read()
CHANGES = open(os.path.join(HERE, 'Changelog')).read()
SHORT_DESCRIPTION = 'snf-quotaholder django app'

PACKAGES_ROOT = '.'
PACKAGES = find_packages(PACKAGES_ROOT, exclude=('test',))

# Package meta
CLASSIFIERS = []
INSTALL_REQUIRES = [
    'Django >=1.2, <1.3',
    'South>=0.7',
    'snf-common',
]

setup(
    name='snf-quotaholder-app',
    version=VERSION,
    license='BSD',
    url='http://www.synnefo.org/',
    description=SHORT_DESCRIPTION,
    long_description=README + '\n\n' + CHANGES,
    classifiers=CLASSIFIERS,

    author='Synnefo development team',
    author_email='synnefo-devel@googlegroups.com',
    maintainer='Synnefo development team',
    maintainer_email='synnefo-devel@googlegroups.com',

    packages=PACKAGES,
    include_package_data=True,
    package_data={
        'quotaholder_django.quotaholder_app': ['fixtures/*.json']
    },
    #scripts = [
    #    'quotaholder_django/quotaholder-manage',
    #],
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    dependency_links=['http://docs.dev.grnet.gr/pypi'],
    entry_points={
     'synnefo': [
         'web_apps = quotaholder_django.synnefo_settings:apps',
         'urls = quotaholder_django.urls:urlpatterns',
         ]
      },
)