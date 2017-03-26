import os
import prefect.configuration

def test_env_vars():
    os.environ['PREFECT__CORE__MY_SETTING'] = '1'
    c = prefect.configuration.load_config(test_mode=True)
    assert c.get('core', 'my_setting') == '1'
