# setup.py
from setuptools import setup, find_packages

setup(
    name="waveassist",
    version="0.0.1",
    author="WaveAssist",
    author_email="kakshil.shah@waveassist.io",
    description="A package for WaveAssist Helper methods",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/waveassist/waveassist.git",
    packages=find_packages(),
    install_requires=[
        "pandas>=1.0.0",
        "requests>=2.0.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
