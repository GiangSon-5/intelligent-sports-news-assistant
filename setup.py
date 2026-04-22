from setuptools import setup, find_packages

setup(
    name="intelligent-sports-assistant",
    version="1.0.0",
    description="Intelligent Sports News Assistant - Auto-crawl, summarize & report Vietnamese sports news",
    author="Sports AI Solutions",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        "Scrapy>=2.11.0",
        "pandas>=2.2.0",
        "langchain>=0.3.0",
        "langchain-google-genai>=2.0.0",
        "langchain-openai>=0.2.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "Jinja2>=3.1.0",
        "markdown>=3.5.0",
        "tenacity>=8.2.0",
        "python-dateutil>=2.8.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "pdf": ["WeasyPrint>=61.0"],
        "dev": ["pytest>=8.0.0", "pytest-mock>=3.12.0"],
    },
)
