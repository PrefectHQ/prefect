# Settings

Prefect's settings are [well-documented][prefect.utilities.settings] and type-validated, ensuring that even configuration is a first-class experience. By modifying these settings, users can customize various aspects of the system. 

From Python, settings can be accessed by examining `prefect.settings`, and users can view their Orion server's current settings from its UI.

## Environment Variables
All settings can be modified via environment variables using the following syntax:
```
[PREFIX]_[SETTING]=value
```

- The `PREFIX` is a string that describes the fully-qualified name of the setting. All prefixes begin with `PREFECT_` and add additional words only to describe nested settings. For example, the prefix for `prefect.settings.home` is just `PREFECT_`, because it is a top-level key in the `settings` object. The prefix for `settings.orion.api.port` is `PREFECT_ORION_API_`, indicating its nested position.
- The `SETTING` corresponds directly to the name of the prefect setting's key. Note that while keys are lowercase, we provide environment variables as uppercase by convention. 

### Examples
A top-level setting:
```shell
# environment variable
PREFECT_HOME="/path/to/home"
```
```python
# python
prefect.settings.home # PosixPath('/path/to/home')
```

A nested setting:

```shell
# environment variable
PREFECT_ORION_API_PORT=4242
```
```python
# python
prefect.settings.orion.api.port # 4242
```
