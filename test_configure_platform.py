import unittest
from unittest.mock import Mock
from configure_platform import configure_curseforge

class LocalPlatformSetupTests(unittest.TestCase):
 def test_key_goes_only_to_platform_update_and_is_not_printed(self):
  store=Mock();lines=[];prompt=Mock(return_value='  fake-test-only-key  ')
  self.assertTrue(configure_curseforge(store,prompt,lines.append))
  store.save.assert_called_once_with({'platformOnly':True,'curseForgeKey':'fake-test-only-key'})
  self.assertNotIn('fake-test-only-key',' '.join(lines))
 def test_empty_input_does_not_clear_existing_key(self):
  store=Mock();self.assertFalse(configure_curseforge(store,lambda _: ' ',lambda _:None));store.save.assert_not_called()
 def test_interrupt_does_not_modify_configuration(self):
  for error in [KeyboardInterrupt,EOFError]:
   store=Mock();self.assertFalse(configure_curseforge(store,Mock(side_effect=error),lambda _:None));store.save.assert_not_called()
 def test_overlong_input_is_not_saved(self):
  store=Mock();self.assertFalse(configure_curseforge(store,lambda _: 'x'*4001,lambda _:None));store.save.assert_not_called()
 def test_failure_never_prints_secret(self):
  store=Mock();store.save.side_effect=ValueError('fake-test-only-key');lines=[]
  self.assertFalse(configure_curseforge(store,lambda _: 'fake-test-only-key',lines.append))
  self.assertNotIn('fake-test-only-key',' '.join(lines))

if __name__=='__main__':unittest.main()
