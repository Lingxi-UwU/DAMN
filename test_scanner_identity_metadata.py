"""Synthetic JAR coverage for locally declared identity hints, without requests."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scanner import scan


class DeclaredIdentityMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.mods = self.root / 'mods'
        self.mods.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def jar(self, name, files):
        with zipfile.ZipFile(self.mods / name, 'w') as jar:
            for filename, value in files.items():
                jar.writestr(filename, value)

    def fabric(self, name='sample.jar', **metadata):
        self.jar(name, {'fabric.mod.json': json.dumps({
            'schemaVersion': 1, 'id': 'sample', 'version': '1.0', **metadata
        })})

    def components(self):
        return scan(self.root)['mods'][0]['components']

    def test_neoforge_preserves_local_mod_and_root_urls(self):
        self.jar('changed-name.jar', {'META-INF/neoforge.mods.toml': '''
modLoader="javafml"
loaderVersion="[1,)"
issueTrackerURL="https://code.example/project/issues"
[[mods]]
modId="sample"
version="1.0"
displayName="Locally changed title"
authors="Declared author"
displayURL="https://code.example/project"
'''})
        component = self.components()[0]
        self.assertEqual(component['authors'], ['Declared author'])
        self.assertEqual(component['projectUrls'], [
            'https://code.example/project', 'https://code.example/project/issues'])
        self.assertEqual(component['name'], 'Locally changed title')
        self.assertEqual(component['source'], 'changed-name.jar!META-INF/neoforge.mods.toml')
        self.assertNotIn('verified', component)

    def test_forge_multimod_keeps_component_authors_separate(self):
        self.jar('bundle.jar', {'META-INF/mods.toml': '''
modLoader="javafml"
loaderVersion="[1,)"
issueTrackerURL="https://code.example/shared/issues"
[[mods]]
modId="first"
version="1.0"
authors=["First", "Second", "First"]
displayURL="https://code.example/first"
[[mods]]
modId="second"
version="1.0"
author="Legacy author"
displayURL="http://code.example/second"
'''})
        first, second = self.components()
        self.assertEqual(first['authors'], ['First', 'Second'])
        self.assertEqual(second['authors'], ['Legacy author'])
        self.assertEqual(first['projectUrls'], [
            'https://code.example/first', 'https://code.example/shared/issues'])
        self.assertEqual(second['projectUrls'], [
            'http://code.example/second', 'https://code.example/shared/issues'])

    def test_fabric_author_objects_strings_and_contact_links(self):
        self.fabric(authors=['First', {'name': 'Second', 'contact': {'email': 'private@example.test'}},
                             'First', {'name': '  Third\nAuthor  '}],
                    contact={'homepage': 'https://example.test/project',
                             'sources': 'https://example.test/source',
                             'issues': 'https://example.test/issues',
                             'email': 'private@example.test',
                             'discord': 'https://example.test/chat'})
        component = self.components()[0]
        self.assertEqual(component['authors'], ['First', 'Second', 'Third Author'])
        self.assertEqual(component['projectUrls'], [
            'https://example.test/project', 'https://example.test/source',
            'https://example.test/issues'])
        self.assertNotIn('private@example.test', json.dumps(component))
        self.assertNotIn('https://example.test/chat', component['projectUrls'])

    def test_legacy_fabric_author_and_missing_fields_are_stable_arrays(self):
        self.fabric(schemaVersion=0, author='Old schema author')
        component = self.components()[0]
        self.assertEqual(component['authors'], ['Old schema author'])
        self.assertEqual(component['projectUrls'], [])
        self.fabric(authors=None, contact=None)
        component = self.components()[0]
        self.assertEqual(component['authors'], [])
        self.assertEqual(component['projectUrls'], [])

    def test_nested_jar_does_not_supply_outer_identity_hints(self):
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, 'w') as jar:
            jar.writestr('fabric.mod.json', json.dumps({
                'id': 'inner', 'version': '1.0', 'authors': ['Inner author'],
                'contact': {'homepage': 'https://example.test/inner'}}))
        self.jar('outer.jar', {
            'fabric.mod.json': json.dumps({'id': 'outer', 'version': '1.0',
                'authors': ['Outer author'], 'contact': {'sources': 'https://example.test/outer'},
                'jars': [{'file': 'META-INF/jars/inner.jar'}]}),
            'META-INF/jars/inner.jar': nested.getvalue()})
        outer, inner = self.components()
        self.assertFalse(outer['nested'])
        self.assertTrue(inner['nested'])
        self.assertEqual(outer['authors'], ['Outer author'])
        self.assertEqual(outer['projectUrls'], ['https://example.test/outer'])
        self.assertEqual(inner['authors'], ['Inner author'])
        self.assertEqual(inner['projectUrls'], ['https://example.test/inner'])
        self.assertNotEqual(outer['source'], inner['source'])

    def test_malformed_author_values_are_bounded_and_do_not_break_scan(self):
        self.fabric(authors=[42, None, {}, {'name': []}, {'name': 5},
                            'a' * 161, 'bad\x00name', ''] +
                           ['Author ' + str(index) for index in range(1000)])
        component = self.components()[0]
        self.assertEqual(len(component['authors']), 16)
        self.assertTrue(all(isinstance(value, str) and len(value) <= 160
                            for value in component['authors']))
        self.assertEqual(component['authors'][0], 'Author 0')
        self.fabric(authors={'unexpected': 'not an author'}, contact=['wrong type'])
        component = self.components()[0]
        self.assertEqual(component['authors'], [])
        self.assertEqual(component['projectUrls'], [])

    def test_malicious_or_malformed_links_never_survive_as_project_urls(self):
        urls = [
            'javascript:alert(1)', 'data:text/html,unsafe', 'file:///C:/private',
            'https://user:secret@example.test/project', 'http://user@example.test',
            'https://example.test/\nforged', 'https://example.test/\x00bad',
            'https://example.test\\path', 'https:///missing-host',
            'https://example.test:broken/path', 'https://example.test:99999/path',
            'https://[bad-ipv6]/path', 'https://bad%40host.test/path',
            'https://example.test/' + 'x' * 2048, None, 4,
            ['https://example.test/not-a-string'], {'url': 'https://example.test/object'}]
        for url in urls:
            with self.subTest(url_type=type(url).__name__):
                self.fabric(contact={'homepage': url})
                self.assertEqual(self.components()[0]['projectUrls'], [])

    def test_static_links_are_deduplicated_and_never_fetched(self):
        self.fabric(authors='Declared author', contact={
            'homepage': ' https://example.test/same ',
            'sources': 'https://example.test/same',
            'issues': 'http://example.test/issues'})
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network allowed')), \
             patch('socket.create_connection', side_effect=AssertionError('No network allowed')):
            component = self.components()[0]
        self.assertEqual(component['projectUrls'], [
            'https://example.test/same', 'http://example.test/issues'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
