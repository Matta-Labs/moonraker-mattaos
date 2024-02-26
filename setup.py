from setuptools import setup, find_packages

setup(
    name="moonraker-mattaos",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "colorlog",
        "Flask",
        "requests",
        "sentry_sdk",
        "websocket-client",
        "psutil",
        "pillow==9.5.0",
        "pandas",
    ],
)
