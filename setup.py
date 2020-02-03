import pathlib
from setuptools import setup

# The directory containing this file

# The text of the README file
README = (pathlib.Path(__file__).parent / "README.md").read_text()

setup(
    name="resguard",
    author="Daniel Hilst Selli",
    author_email="danielhilst@gmail.com",
    version="0.12",
    py_modules=["resguard"],
    python_requires=">=3.6",
    long_description=README,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    url="https://github.com/dhilst/resguard",
    install_requires=[
        "dataclasses;python_version<'3.7'",
        "typing_extensions;python_version<'3.8'",
    ],
    extras_require={
        'tests': ['requests', 'dataclass;python_version<="3.6"'],
    },
    test_suite="resguard",
)
