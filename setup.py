from setuptools import setup, find_packages
import os

# Read README.md safely
this_directory = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(this_directory, "README.md")

with open(readme_path, encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="waveassist",
    version="0.2.0",
    author="WaveAssist",
    author_email="kakshil.shah@waveassist.io",
    description="WaveAssist Python SDK for storing and retrieving structured data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/waveassist/waveassist",
    packages=find_packages(exclude=["tests*", "*.tests"]),
    include_package_data=True,
    install_requires=["pandas>=1.0.0", "requests>=2.32.4", "python-dotenv>=1.1.1"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "waveassist=waveassist.cli:main",  # this line enables `waveassist` CLI
        ]
    },
)
