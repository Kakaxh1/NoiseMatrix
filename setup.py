#!/usr/bin/env python3
"""
Setup script for WiFi Jammer
"""

from setuptools import setup, find_packages
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

setup(
    name="wifi-jammer",
    version="1.0.0",
    author="Your Name",
    description="WiFi Deauthentication Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "wifi-jammer=src.main:main",
        ],
    },
    include_package_data=True,
)