import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pysaj",
    version="0.0.1",
    author="fredericvl",
    author_email="frederic.van.linthoudt@gmail.com",
    description="Library to communicate with SAJ inverters",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fredericvl/pysaj",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
