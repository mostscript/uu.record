from setuptools import setup, find_packages
import os

version = '0.1dev'

setup(name='uu.record',
      version=version,
      description="Components for persistent data records within a CMF context.",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      classifiers=[
        "Programming Language :: Python",
        "Intended Audience :: Developers",
        "Framework :: Plone",
        ],
      keywords='',
      author='Sean Upton',
      author_email='sean.upton@hsc.utah.edu',
      url='http://launchpad.net/upiq',
      license='MIT',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['uu'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'zope.schema>=3.8.0',
          'zope.lifecycleevent',
          'Products.CMFCore',
          # -*- Extra requirements: -*-
      ],
      extras_require = {
          'test': [ 'plone.testing>=4.0a6', ],
      },
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )

