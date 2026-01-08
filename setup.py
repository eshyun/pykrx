from setuptools import setup, find_packages
import tomllib

with open("readme.MD", "r", encoding='UTF-8') as fh:
    long_description = fh.read()

with open("pyproject.toml", "rb") as fh:
    version = tomllib.load(fh)["project"]["version"]

setup(
    name='pykrx',
    version=version,
    description='KRX data scraping',
    url='https://github.com/sharebook-kr/pykrx/',
    author='Brayden Jo, Jonghun Yoo',
    author_email=('brayden.jo@outlook.com, '
                  'jonghun.yoo@outlook.com, '
                  'pystock@outlook.com'),
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=['requests', 'pandas', 'datetime', 'numpy', 'xlrd',
                      'deprecated', 'multipledispatch', 'matplotlib'],
    license='MIT',
    packages=find_packages(include=['pykrx', 'pykrx.*']),
    package_data={
        'pykrx': ['*.ttf'],
    },
    python_requires='>=3',
    zip_safe=False
)
