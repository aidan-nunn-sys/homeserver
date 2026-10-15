import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sanitize import Sanitizer, dashed, fill, norm_guid, slug

IP = '.'.join(['192', '168', '7', '7'])
USER_ID = 'ab' * 16
LIB_ID = 'cd' * 16
ITEM_ID = 'ef' * 16
DOMAIN = 'example.org'
EMAIL_ADDR = 'someone' + '@' + DOMAIN


def make(env=None):
    return Sanitizer(env or {}, domains=[DOMAIN], users=[('alice', USER_ID)],
                     libraries=[('Movies', LIB_ID)],
                     literals={'MEDIA_ROOT': '/srv/media'})


class HelpersTest(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slug('Home Screen Sections'), 'HOME_SCREEN_SECTIONS')

    def test_guid_forms(self):
        self.assertEqual(norm_guid(dashed(USER_ID)), USER_ID)
        self.assertEqual(len(dashed(USER_ID)), 36)

    def test_fill_replaces_known_and_keeps_unknown(self):
        out = fill({'<A>': ['x <A> <B>']}, {'A': '1'})
        self.assertEqual(out, {'1': ['x 1 <B>']})


class SanitizerTest(unittest.TestCase):
    def test_secret_field_replaced_and_recorded(self):
        s = make()
        out = s.sanitize({'Sonarr': {'ApiKey': 'fake-key-1'}}, 'Home Screen Sections')
        self.assertEqual(out, {'Sonarr': {'ApiKey': '<HOME_SCREEN_SECTIONS_SONARR_APIKEY>'}})
        self.assertEqual(s.new['HOME_SCREEN_SECTIONS_SONARR_APIKEY'], 'fake-key-1')

    def test_plain_key_fields_are_not_secrets(self):
        out = make().sanitize({'Key': 'RefreshLibrary', 'SortKey': 'Name'}, 'x')
        self.assertEqual(out, {'Key': 'RefreshLibrary', 'SortKey': 'Name'})

    def test_empty_secret_left_alone(self):
        self.assertEqual(make().sanitize({'ApiKey': ''}, 'x'), {'ApiKey': ''})

    def test_query_string_token_replaced(self):
        s = make()
        out = s.sanitize({'Webhook': 'https://hooks.example.net/x?a=1&token=fake-tok'}, 'P')
        self.assertEqual(out['Webhook'], 'https://hooks.example.net/x?a=1&token=<P_WEBHOOK_QUERY_TOKEN>')
        self.assertEqual(s.new['P_WEBHOOK_QUERY_TOKEN'], 'fake-tok')

    def test_ip_domain_email_replaced(self):
        s = make()
        out = s.sanitize({'Url': IP + ':8989', 'Ext': 'https://requests.' + DOMAIN + '/x',
                          'Mail': EMAIL_ADDR}, 'P')
        self.assertEqual(out, {'Url': '<HOST_1>:8989', 'Ext': 'https://<DOMAIN_1>/x',
                               'Mail': '<EMAIL_1>'})
        self.assertEqual(s.new['HOST_1'], IP)
        self.assertEqual(s.new['DOMAIN_1'], 'requests.' + DOMAIN)

    def test_users_names_and_ids(self):
        s = make()
        out = s.sanitize({'alice': {'UserId': USER_ID, 'Owner': dashed(USER_ID)}}, 'P')
        self.assertEqual(out, {'<USER_1>': {'UserId': '<USER_1_ID>', 'Owner': '<USER_1_GUID>'}})
        self.assertEqual(s.new['USER_1'], 'alice')
        self.assertEqual(s.new['USER_1_ID'], USER_ID)

    def test_library_id_replaced_not_stored(self):
        s = make()
        out = s.sanitize({'DefaultMoviesLibraryId': LIB_ID}, 'P')
        self.assertEqual(out, {'DefaultMoviesLibraryId': '<LIBRARY_MOVIES_ID>'})
        self.assertNotIn(LIB_ID, s.new.values())

    def test_item_id_in_id_field_kept_and_allowlisted(self):
        s = make()
        out = s.sanitize({'PinnedItemIds': [ITEM_ID], 'Id': dashed(ITEM_ID)}, 'P')
        self.assertEqual(out, {'PinnedItemIds': [ITEM_ID], 'Id': dashed(ITEM_ID)})
        self.assertEqual(s.kept_ids, {ITEM_ID})

    def test_hex_in_non_id_field_becomes_placeholder(self):
        s = make()
        out = s.sanitize({'Notes': 'use ' + ITEM_ID}, 'P')
        self.assertEqual(out, {'Notes': 'use <HEX_1>'})
        self.assertEqual(s.kept_ids, set())

    def test_literal_path_replaced(self):
        out = make().sanitize({'Path': '/srv/media/Movies'}, 'P')
        self.assertEqual(out, {'Path': '<MEDIA_ROOT>/Movies'})

    def test_numbering_is_stable_with_existing_env(self):
        s = make({'HOST_1': '.'.join(['10', '0', '0', '9']), 'HOST_2': IP})
        out = s.sanitize({'Url': IP}, 'P')
        self.assertEqual(out, {'Url': '<HOST_2>'})
        self.assertNotIn('HOST_3', s.new)

    def test_used_tracks_placeholders(self):
        s = make()
        s.sanitize({'Url': IP, 'Path': '/srv/media/x'}, 'P')
        self.assertEqual(s.used, {'HOST_1', 'MEDIA_ROOT'})

    def test_round_trip(self):
        s = make()
        original = {'alice': {'ApiKey': 'k1', 'Url': IP, 'Lib': LIB_ID, 'Mail': EMAIL_ADDR,
                              'Path': '/srv/media/Movies', 'Notes': ITEM_ID}}
        out = s.sanitize(original, 'P')
        values = dict(s.env)
        values['LIBRARY_MOVIES_ID'] = LIB_ID
        self.assertEqual(fill(out, values), original)


if __name__ == '__main__':
    unittest.main()
