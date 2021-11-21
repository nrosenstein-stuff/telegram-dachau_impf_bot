# This file was auto-generated by Shut. DO NOT EDIT
# For more information about Shut, check out https://pypi.org/project/shut/

from __future__ import print_function
import io
import os
import setuptools
import sys

readme_file = 'readme.md'
if os.path.isfile(readme_file):
  with io.open(readme_file, encoding='utf8') as fp:
    long_description = fp.read()
else:
  print("warning: file \"{}\" does not exist.".format(readme_file), file=sys.stderr)
  long_description = None

requirements = [
  'sqlalchemy',
  'sqlalchemy-repr',
  'python-telegram-bot',
  'requests',
  'bs4 >=0.0.1,<1.0.0',
  'databind.core >=0.11.0,<1.0.0',
  'databind.yaml >=0.1.3,<1.0.0',
  'nr.stream >=0.1.2,<1.0.0',
  'prometheus-client >=0.11.0,<1.0.0',
]

setuptools.setup(
  name = 'impfbot',
  version = '1.2.1',
  author = 'Niklas Rosenstein',
  author_email = 'rosensteinniklas@gmail.com',
  description = 'Package description here.',
  long_description = long_description,
  long_description_content_type = 'text/markdown',
  url = None,
  license = None,
  packages = setuptools.find_packages('src', ['test', 'test.*', 'tests', 'tests.*', 'docs', 'docs.*']),
  package_dir = {'': 'src'},
  include_package_data = True,
  install_requires = requirements,
  extras_require = {},
  tests_require = [],
  python_requires = '>=3.5.0,<4.0.0',
  data_files = [],
  entry_points = {
    'impfbot.api.IPlugin': [
      'dachau = impfbot.contrib.de.bavaria.dachau:DachauMedPlugin',
    ]
  },
  cmdclass = {},
  keywords = [],
  classifiers = [],
  zip_safe = True,
)
