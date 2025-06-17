#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EVOSEAL - An advanced AI system integrating DGM, OpenEvolve, and SEAL.
"""

import os
import sys
from pathlib import Path

from setuptools import find_packages, setup

# Read requirements from requirements.txt
def read_requirements(req_file):
    with open(req_file, encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith(("#", "-r", "--"))
        ]

# Read the README for the long description
this_dir = Path(__file__).parent
with open(this_dir / "README.md", encoding="utf-8") as f:
    long_description = f.read()

# Get version
version = {}
with open(this_dir / "evoseal" / "__version__.py", encoding="utf-8") as f:
    exec(f.read(), version)

# Setup configuration
setup(
    name="evoseal",
    version=version["__version__"],
    description="An advanced AI system integrating DGM, OpenEvolve, and SEAL",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Kresna Sucandra",
    author_email="kresna@evoseal.ai",
    url="https://github.com/yourusername/evoseal",
    packages=find_packages(exclude=["tests*"]),
    package_data={"evoseal": ["py.typed"]},
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("requirements/dev.txt"),
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Typing :: Typed",
    ],
    entry_points={
        "console_scripts": [
            "evoseal=evoseal.cli:main",
        ],
    },
    zip_safe=False,
    keywords="ai machine-learning evolutionary-algorithms dgm openevolve seal",
    project_urls={
        "Documentation": "https://evoseal.readthedocs.io",
        "Source": "https://github.com/yourusername/evoseal",
        "Bug Reports": "https://github.com/yourusername/evoseal/issues",
    },
)
