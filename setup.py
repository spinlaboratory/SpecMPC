import setuptools

with open('README.md','r') as f:
    long_description = f.read()

with open("pyB12SMC/version.py", "r") as f:
    # Define __version__
    exec(f.read())

setuptools.setup(
    name='pyB12SMC',
    version=__version__,
    author='Bridge12 Technologies, Inc',
    author_email='yhuang@bridge12.com',
    description='A python package for interfacing with Stepper Motor Controller (BIGTREETECH SKR MINI E3 V3.0) used in Bridge 12 Technologies products.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='http://www.bridge12.com/',
    project_urls={
        'Source Code':'https://github.com/Bridge12Technologies/pyB12SMC',
        },
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
    install_requires=['numpy >= 1.26.2', 'pyserial >= 3.5'],
)