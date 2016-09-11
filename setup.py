import setuptools

setuptools.setup(
    name = 'remotedownload-dropbox',
    version = '1.0.0dev',
    packages = setuptools.find_packages(),
    entry_points = {'console_scripts': [
        'remotedownload-dropbox = remotedownloaddropbox.__main__:main',
    ]},
    install_requires = ['remotedownload', 'dropbox'],
)
