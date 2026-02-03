from setuptools import setup, find_packages

setup(
    name="polymarket-bot-tournament",
    version="0.1.0",
    description="Read-only Polymarket API integration for paper trading tournament",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pandas>=2.0.0",
    ],
    python_requires=">=3.8",
)
