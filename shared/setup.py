from setuptools import setup, find_packages

setup(
    name="eduzim-shared",
    version="1.0.0",
    description="Shared libraries for EduZim microservices",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "confluent-kafka>=2.3.0",
        "pydantic>=2.0.0",
        "fastapi>=0.109.0",
    ],
)
