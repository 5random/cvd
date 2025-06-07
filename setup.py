from setuptools import setup, find_packages
from glob import glob

setup(
    name='cvd',
    version='0.1.0',
    install_requires=[
        'plotly',
        'nicegui',
        'numpy',
        'pyserial',
        'opencv-python',
        'Pillow',
        'pytest',
        'pytest-asyncio',
        'watchdog',
        'jsonschema',
    ],
    packages=find_packages('program'),
    package_dir={'': 'program'},
    data_files=[
        ('cvd/config', glob('config/*.json')),
        ('cvd/data', ['data/data_index.json']),
        ('cvd/data/logs', glob('data/logs/*.log')),
        ('cvd/data/notifications', glob('data/notifications/*.json')),
    ],
)
