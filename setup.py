from os.path import dirname, abspath, join, exists
from setuptools import setup, find_packages


long_description = None
if exists("README.md"):
    long_description = open("README.md").read()


setup(
  name="grippin",
  packages=find_packages(),
  description="Simple gRPC Server Framework",
  long_description=long_description,
  author="Sangwon Lee",
  author_email="gamzabaw@gmail.com",
  version="0.2.5",
  license="MIT License",
  zip_safe=False,
  include_package_data=True,
  install_requires=[
    "grpcio==1.22.0",
    "grpcio-reflection==1.22.0",
    "grpcio-tools==1.22.0",
    "grpcio-opentracing==1.1.4",
    "google-api-python-client==1.7.10"
  ],
  url="https://github.com/sangwonl/grippin",
  tests_require=["unittest2"],
  test_suite="tests.my_module_suite",
  classifiers = [
    "Programming Language :: Python :: 3",
    "Environment :: Other Environment",
    "Intended Audience :: Developers",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries :: Python Modules",
  ],
)
