from setuptools import setup, find_packages


setup(
    name="md2confluence",
    version="0.1.0",
    description="Import Markdown documents into Confluence wiki.",
    author="Daniel Kertesz",
    author_email="daniel@spatof.org",
    url="https://github.com/piger/md2confluence",
    install_requires=[
        'mistune==0.7.4',
        'requests==2.20.0',
    ],
    include_package_data=True,
    packages=find_packages(),
    entry_points="""
    [console_scripts]
    md2confluence = md2confluence.main:main
    """
)
