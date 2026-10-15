"""Replace identifying values in Jellyfin config with <PLACEHOLDER> names.

Every real value is recorded (Sanitizer.env / .new) so restore.py can put it
back; the sanitized output contains no identifying values.
"""
import re

SECRET_KEY = re.compile(r'(?:api|auth|access|private|license|client)_?key|token|password|passwd|secret', re.I)
SECRET_QUERY = re.compile(r'([?&](?:api_?key|access_token|token|password)=)([^&\s"\'<>]+)', re.I)
PRIVATE_IP = re.compile(
    r'\b(?:10(?:\.\d{1,3}){3}|127(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}'
    r'|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
GUID = re.compile(
    r'\b(?:[0-9a-fA-F]{32}'
    r'|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b')
PLACEHOLDER = re.compile(r'<([A-Z][A-Z0-9_]*)>')
ID_FIELD = re.compile(r'ids?$', re.I)


def slug(text):
    return re.sub(r'[^A-Z0-9]+', '_', text.upper()).strip('_')


def norm_guid(text):
    return text.replace('-', '').lower()


def dashed(guid):
    g = norm_guid(guid)
    return f'{g[:8]}-{g[8:12]}-{g[12:16]}-{g[16:20]}-{g[20:]}'


def fill(obj, values):
    if isinstance(obj, dict):
        return {fill(k, values): fill(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill(v, values) for v in obj]
    if isinstance(obj, str):
        return PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), obj)
    return obj


class Sanitizer:
    def __init__(self, env, domains=(), users=(), libraries=(), literals=None):
        self.env = dict(env)
        self.new = {}
        self.used = set()
        self.kept_ids = set()
        self._by_value = {}
        for key, value in self.env.items():
            self._by_value.setdefault(value, []).append(key)
        self._ids = {}
        self._user_names = {}
        for name, uid in users:
            placeholder = self._name_for(name, 'USER')
            self._user_names[name] = placeholder
            self._remember(f'{placeholder}_ID', norm_guid(uid))
            self._ids[norm_guid(uid)] = placeholder
        for name, lid in libraries:
            self._ids[norm_guid(lid)] = f'LIBRARY_{slug(name)}'
        self._literals = []
        for name, value in (literals or {}).items():
            if value:
                self._remember(name, value)
                self._literals.append((name, value))
        self._literals.sort(key=lambda item: -len(item[1]))
        self._domains = [
            re.compile(r'(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)*' + re.escape(d) + r'(?![A-Za-z0-9-])', re.I)
            for d in domains if d]

    def sanitize(self, obj, context):
        return self._walk(obj, [slug(context)])

    def _remember(self, name, value):
        if self.env.get(name) != value:
            self.env[name] = value
            self.new[name] = value
            self._by_value.setdefault(value, []).append(name)

    def _name_for(self, value, prefix):
        pattern = re.compile(re.escape(prefix) + r'_(\d+)')
        for key in self._by_value.get(value, []):
            if pattern.fullmatch(key):
                return key
        taken = [int(m.group(1)) for key in self.env if (m := pattern.fullmatch(key))]
        name = f'{prefix}_{max(taken, default=0) + 1}'
        self._remember(name, value)
        return name

    def _ph(self, name):
        self.used.add(name)
        return f'<{name}>'

    def _secret(self, path, value):
        name = slug('_'.join(path))
        self._remember(name, value)
        return self._ph(name)

    def _walk(self, obj, path):
        if isinstance(obj, dict):
            out = {}
            for key, value in obj.items():
                new_key = self._text(key, path + [key], is_key=True) if isinstance(key, str) else key
                if (isinstance(value, str) and value and isinstance(key, str)
                        and SECRET_KEY.search(key) and not PLACEHOLDER.fullmatch(value)):
                    out[new_key] = self._secret(path + [new_key], value)
                else:
                    out[new_key] = self._walk(value, path + [new_key])
            return out
        if isinstance(obj, list):
            return [self._walk(value, path + [str(i)]) for i, value in enumerate(obj)]
        if isinstance(obj, str):
            return self._text(obj, path)
        return obj

    def _text(self, text, path, is_key=False):
        if text in self._user_names:
            return self._ph(self._user_names[text])
        for name, value in self._literals:
            if value in text:
                text = text.replace(value, self._ph(name))
        text = SECRET_QUERY.sub(
            lambda m: m.group(1) + self._secret(path + ['QUERY', m.group(1).strip('?&=')], m.group(2)),
            text)
        text = EMAIL.sub(lambda m: self._ph(self._name_for(m.group(0), 'EMAIL')), text)
        for domain in self._domains:
            text = domain.sub(lambda m: self._ph(self._name_for(m.group(0), 'DOMAIN')), text)
        text = PRIVATE_IP.sub(lambda m: self._ph(self._name_for(m.group(0), 'HOST')), text)
        field = next((p for p in reversed(path) if not p.isdigit()), '')
        return GUID.sub(lambda m: self._guid(m.group(0), field, is_key), text)

    def _guid(self, text, field, is_key):
        guid = norm_guid(text)
        suffix = 'GUID' if '-' in text else 'ID'
        if guid in self._ids:
            return self._ph(f'{self._ids[guid]}_{suffix}')
        if is_key or ID_FIELD.search(field):
            self.kept_ids.add(guid)
            return text
        return self._ph(self._name_for(text, 'HEX'))
