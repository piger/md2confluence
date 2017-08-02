from setuptools import setup, find_packages


setup(
    name="md2confluence",
    version="0.1.0",
    description="Import Markdown documents into Confluence wiki.",
    author="Daniel Kertesz",
    author_email="daniel@spatof.org",
    url="https://github.com/piger/md2confluence",
    install_requires=[
        #'click==6.7',
        'mistune==0.7.4',
        'requests==2.18.3',
    ],
    include_package_data=True,
    zip_safe=False,
    packages=find_packages(),
    entry_points="""
    [console_scripts]
    md2confluence = md2confluence.main:main
    """
)
