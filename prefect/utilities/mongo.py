import mongoengine

def reload_or_save(model):
    """
    Given a model with the primary key set, attempts to reload all
    values from the database. If the model isn't in the database, saves it
    as is.

    This is useful when initializing a model with an ORM analogue:

    def __init__(self, *args, **kwargs):
        self.orm = ORMModel(_id=orm_id)
        reload_or_create(model)

    If the model already exists, the ORM model is loaded with the latest
    information from the database. If it doesn't exist, it is created.
    """
    try:
        model.reload()
    except mongoengine.DoesNotExist:
        model.save()
