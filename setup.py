from setuptools import setup, find_packages

setup(
    name="moonraker-mattaos",
    version="0.1.2",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "colorlog",
        "Flask",
        "requests",
        "sentry-sdk==1.41.0",
        "websocket-client==1.7.0",
        "psutil",
        "pillow==9.5.0",
        "pandas==1.3.5",
        "numpy",
    ],
)
