from setuptools import setup, find_packages

setup(
    name='cryptonomicon',
    version='1.0',
    packages=find_packages(),
    package_dir={'cryptonomicon': ''},
    package_data={
        'cryptonomicon': []
    },
    scripts=[
    ],
    install_requires=[
        "ws4py~=0.5.1",
        "Flask~=1.0.2",
        "Flask-Cors~=3.0.3",
        "Flask-SocketIO~=3.0.0",
        "gevent~=1.2.2",
        "gevent-websocket~=0.10.1",
    ]
)
