from setuptools import setup, find_packages

setup(
    name="appscraper",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "Flask>=3.1.0",
        "Werkzeug>=3.1.3",
        "flask-login>=0.6.3",
        "python-dotenv>=1.0.1",
        "pymongo>=4.10.1",
        "bcrypt>=4.2.1",
        "beautifulsoup4>=4.12.3",
        "requests>=2.32.3",
        "Pillow>=11.0.0",
        "gunicorn>=23.0.0",
        "Authlib>=1.3.2",
        "Flask-Caching>=2.1.0"
    ],
) 