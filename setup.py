import setuptools

with open('README.md','r') as f:
    long_description = f.read()

with open("pySMC/version.py", "r") as f:
    # Define __version__
    exec(f.read())

setuptools.setup(
    name='pySMC',
    version=__version__,
    author='Bruker BioSpin',
    author_email='yen-chun.huang@bruker.com',
    description='A Python package for interfacing with Stepper Motor Controller (BIGTREETECH SKR MINI E3 V3.0) used in Bridge12 products.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    project_urls={
        'Source Code':'https://github.com/spinlaboratory/pySMC',
        },
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
    install_requires=['numpy >= 1.26.2', 'pyserial >= 3.5'],
)