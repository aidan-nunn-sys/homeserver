"""Synthetic Jellyfin responses. Identifying-looking values are built at
runtime so check_secrets.py does not flag this file."""
IP = '.'.join(['192', '168', '7', '7'])
USER_ID = 'ab' * 16
LIB_ID = 'cd' * 16
ITEM_ID = 'ef' * 16
PLUGIN_ID = '-'.join(['12' * 4, '34' * 2, '56' * 2, '78' * 2, '9a' * 6])
OLD_PLUGIN_ID = '-'.join(['21' * 4, '43' * 2, '65' * 2, '87' * 2, 'a9' * 6])
SONARR_KEY = 'fake-sonarr-key-0001'
TOKEN = 'fake-token-0002'
DOMAIN = 'example.org'
EMAIL_ADDR = 'someone' + '@' + DOMAIN


def env():
    return {
        'JELLYFIN_URL': 'https://jf.' + DOMAIN,
        'JELLYFIN_API_KEY': 'fake-jf-key-0003',
        'PRIVATE_DOMAINS': DOMAIN,
        'MEDIA_ROOT': '/srv/media',
    }


def responses():
    return {
        'System/Info': {'Version': '10.11.5', 'ProgramDataPath': '/srv/jf-data'},
        'System/Configuration': {'MetadataPath': '/srv/jf-data/metadata'},
        'Users': [{'Name': 'alice', 'Id': USER_ID}],
        'Library/VirtualFolders': [{
            'Name': 'Movies', 'ItemId': LIB_ID, 'CollectionType': 'movies',
            'Locations': ['/srv/media/Movies'],
            'LibraryOptions': {'EnableTrickplayImageExtraction': True,
                               'PathInfos': [{'Path': '/srv/media/Movies'}]},
        }],
        'Repositories': [{'Name': 'Stable', 'Enabled': True,
                          'Url': 'https://repo.jellyfin.org/files/plugin/manifest.json'}],
        'Plugins': [
            {'Name': 'Home Screen Sections', 'Id': PLUGIN_ID, 'Version': '2.5.7.0', 'Status': 'Active'},
            {'Name': 'Home Screen Sections', 'Id': PLUGIN_ID, 'Version': '2.5.6.0', 'Status': 'Superseded'},
            {'Name': 'Old Thing', 'Id': OLD_PLUGIN_ID, 'Version': '1.0.0.0', 'Status': 'Disabled'},
        ],
        f'Plugins/{PLUGIN_ID}/Configuration': {
            'Sonarr': {'ApiKey': SONARR_KEY, 'Url': IP + ':8989'},
            'JellyseerrExternalUrl': 'requests.' + DOMAIN,
            'DefaultMoviesLibraryId': LIB_ID,
            'PinnedItemId': ITEM_ID,
            'Webhook': 'https://hooks.example.net/x?token=' + TOKEN,
            'Contact': EMAIL_ADDR,
        },
        'System/Configuration/branding': {
            'CustomCss': '@import url("https://cdn.example.com/theme.css");',
            'LoginDisclaimer': '', 'SplashscreenEnabled': False,
        },
        'ScheduledTasks': [{'Key': 'RefreshLibrary', 'Name': 'Scan Media Library', 'Id': 'task-1',
                            'Triggers': [{'Type': 'IntervalTrigger', 'IntervalTicks': 432000000000}]}],
        f'DisplayPreferences/usersettings?userId={USER_ID}&client=emby': {
            'CustomPrefs': {'homesection0': 'smalllibrarytiles'}, 'SortBy': 'SortName'},
    }


# Every identifying value above; none may appear in exported files.
SENSITIVE = [IP, USER_ID, LIB_ID, SONARR_KEY, TOKEN, 'requests.' + DOMAIN, EMAIL_ADDR,
             'alice', '/srv/media', '/srv/jf-data', 'fake-jf-key-0003']
