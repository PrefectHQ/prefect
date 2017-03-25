import configparser
import os


def expand(env_var):
    """
    Expands (potentially nested) env vars by repeatedly applying
    `expandvars` and `expanduser` until interpolation stops having
    any effect.
    """
    if not env_var:
        return env_var
    while True:
        interpolated = os.path.expanduser(os.path.expandvars(str(env_var)))
        if interpolated == env_var:
            return interpolated
        else:
            env_var = interpolated


class PrefectConfigParser(configparser.ConfigParser):
    """
    A ConfigParser that can also use environment variables, if they exist.

    An environment variable of the form PREFECT__<SECTION>__<KEY> (note
    the double underscore)
    """

    def _get_env_var(self, section, key):
        env_var = 'PREFECT__{S}__{K}'.format(S=section.upper(), K=key.upper())
        if env_var in os.environ:
            return expand(os.environ[env_var])

    def get(self, section, key, **kwargs):
        section = section.lower()
        key = key.lower()

        # first check env vars
        option = self._get_env_var(section, key)
        if option:
            return option

        # then the config file
        return super().get(section, key, **kwargs)


PREFECT_DIR = expand(os.getenv('PREFECT_DIR', '~/.prefect'))
PREFECT_CONFIG = expand(
    os.getenv('PREFECT_CONFIG', os.path.join(PREFECT_DIR, 'prefect.cfg')))
_default_config_file = os.path.join(
    os.path.dirname(__file__), 'config_templates', 'prefect.cfg')

with open(_default_config_file, 'r') as f:
    DEFAULT_CONFIG = f.read()

os.makedirs(PREFECT_DIR, exist_ok=True)
if not os.path.isfile(PREFECT_CONFIG):
    with open(PREFECT_CONFIG, 'w') as f:
        f.write(DEFAULT_CONFIG)

config = PrefectConfigParser()
config.read_string(DEFAULT_CONFIG)
config.read_file(open(PREFECT_CONFIG, 'r'))
