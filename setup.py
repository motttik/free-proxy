import setuptools
from pathlib import Path

# Читаем README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Читаем версию
version_content = (this_directory / "fp" / "__init__.py").read_text(encoding="utf-8")
for line in version_content.split("\n"):
    if line.startswith("__version__"):
        version = line.split("=")[1].strip().strip('"')
        break
else:
    version = "2.0.0"

setuptools.setup(
    name="free-proxy",
    version=version,
    author="jundymek, Qwen Code AI",
    author_email="jundymek@gmail.com",
    description="Free proxy scraper and checker with 50+ sources, async support, and CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jundymek/free-proxy",
    project_urls={
        "Bug Tracker": "https://github.com/jundymek/free-proxy/issues",
        "Documentation": "https://github.com/jundymek/free-proxy#readme",
        "Source": "https://github.com/jundymek/free-proxy",
    },
    packages=setuptools.find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: Proxy Servers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3 :: Only",
        "Typing :: Typed",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Framework :: AsyncIO",
    ],
    python_requires=">=3.8",
    install_requires=[
        "lxml>=5.0.0",
        "requests>=2.31.0",
        "aiohttp>=3.9.0",
        "httpx[socks]>=0.25.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "aiosqlite>=0.22.0",
        "apscheduler>=3.11.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.23.0",
            "mypy>=1.8.0",
            "black>=24.0.0",
            "ruff>=0.1.0",
        ],
        "socks": ["PySocks>=1.7.1"],
        "progress": ["tqdm>=4.66.0"],
    },
    entry_points={
        "console_scripts": [
            "fp=fp.cli:app",
            "free-proxy=fp.cli:app",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords=[
        "proxy",
        "free proxy",
        "proxy scraper",
        "proxy checker",
        "http proxy",
        "https proxy",
        "socks proxy",
        "web scraping",
        "async",
        "cli",
    ],
)
