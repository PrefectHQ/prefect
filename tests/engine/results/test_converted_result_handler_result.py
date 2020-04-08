class TestConvertedResultHandlerResultFromEngineResultHandlers:
    """
    Tests for when we instantiate a different Result subclass based on a user passing in a configured Core engine result handler.
    """

    def test_from_s3_result_handler(self):
        assert False
        # give this a s3 result handler and make sure it converts to an S3Result we like
        # mix it up with different config based on required/non required S3 result handler config we expect

    def test_from_gcs_result_handler(self):
        assert False
        # do this for everyone
        # maybe use pytest parameterize if its not cray


class TestConvertedResultHandlerResultFromCustomResultHandler:
    """
    Tests for when we actually instantiate a ConvertedResultHandlerResult class off of a user's custom result handler.
    """

    def test_from_custom_result_handler(self):
        assert False
        # when we actually make a conversion because they defined a custom result handler

    def test_read(self):
        assert False

    def test_write(self):
        assert False
