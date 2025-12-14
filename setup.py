from setuptools import setup, find_packages
import os

# Read README.md safely
this_directory = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(this_directory, "README.md")

with open(readme_path, encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="waveassist",
    version="0.3.1",
    author="WaveAssist",
    author_email="kakshil.shah@waveassist.io",
    description="WaveAssist Python SDK for storing and retrieving structured data, LLM integration, and credit management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/waveassist/waveassist",
    packages=find_packages(exclude=["tests*", "*.tests"]),
    include_package_data=True,
    install_requires=["pandas>=1.0.0", "requests>=2.32.4", "python-dotenv>=1.1.1", "instructor>=1.13.0", "openai>=2.11.0"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "waveassist=waveassist.cli:main",  # this line enables `waveassist` CLI
        ]
    },
)
