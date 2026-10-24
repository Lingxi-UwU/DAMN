"""Shared release metadata for the runnable public source edition."""

VERSION = '0.5.6'
EDITION = 'public-source'
DATA_DIRECTORY_NAME = 'DAMN-Public'
USER_DATA_SUBDIRECTORY = '.damn-public-user'


def render_version(template):
    """Resolve trusted UI templates before they reach the renderer."""
    return template.replace('__VERSION__', VERSION)
