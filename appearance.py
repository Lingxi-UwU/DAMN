"""Fixed public appearance contract; no appearance state is stored."""
from pathlib import Path


class AppearanceStore:
    """Expose the default forest appearance for the public source edition."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def public(self):
        return {'theme': 'forest', 'available': False, 'edition': 'public-source',
                'status': 'unavailable', 'code': 'public_feature_unavailable'}

    def record_analysis(self, report):
        return None
