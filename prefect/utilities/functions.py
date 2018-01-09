# For optional function arguments that can accept None as a valid value,
# this sentinel can be used as the default value instead.
# Normally, one could simply use object() as the sentine, but that won't
# survive serialization.
OPTIONAL_ARGUMENT = '__OPTIONAL__'
