from setuptools import setup, find_packages

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
)
