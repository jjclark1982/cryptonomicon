from setuptools import setup, find_packages

setup(
    name='cryptonomicon',
    version='1.0',
    packages=find_packages(),
    package_dir={'': 'src'},
    package_data={
        'cryptonomicon': []
    },
    scripts=[
    ],
    install_requires=[
        "ws4py>=0.4.3",
        "Flask>=0.12.2",
        "Flask-Cors>=3.0.3",
        "Flask-SocketIO>=2.9.3",
    ]
)
