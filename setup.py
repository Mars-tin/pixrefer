from setuptools import setup, find_packages

setup(
    name="pixrefer",
    version="0.1.0",
    description="A package for annotating images with bounding boxes and generating descriptions using GPT models",
    author="Jing Ding",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "matplotlib",
        "pillow",
        "openai",
        "pyyaml",
        "google"
    ],
    python_requires=">=3.6",
) 