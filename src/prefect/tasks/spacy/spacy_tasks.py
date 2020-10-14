import spacy

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SpacyNLP(Task):
    """
    Task for processing text with a spaCy pipeline.

    Args:
        - text (unicode, optional): string to be processed, can be provided during construction
            or when task is run
        - nlp (spaCy text processing pipeline, optional): a custom spaCy text
            processing pipeline, if provided, this pipeline will be used instead
            of being created from spacy_model_name
        - spacy_model_name (str, optional): name of the spaCy language model, default
            model is 'en_core_web_sm', will be ignored if nlp is provided
        - disable (List[str], optional): list of pipeline components
            to disable, only applicable to pipelines loaded from spacy_model_name
        - component_cfg (dict, optional): a dictionary with extra keyword
            arguments for specific components, only applicable to pipelines loaded from
            spacy_model_name
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        text: str = u"",
        nlp=None,
        spacy_model_name: str = "en_core_web_sm",
        disable: list = None,
        component_cfg: dict = None,
        **kwargs
    ):
        self.text = text
        self.disable = disable or []
        self.component_cfg = component_cfg or {}

        # load spacy model
        if nlp:
            self.nlp = nlp
        else:
            try:
                self.nlp = spacy.load(
                    spacy_model_name,
                    disable=self.disable,
                    component_cfg=self.component_cfg,
                )
            except IOError as exc:
                raise ValueError(
                    "spaCy model %s not found." % spacy_model_name
                ) from exc

        super().__init__(**kwargs)

    @defaults_from_attrs("text")
    def run(self, text: str = u""):
        """
        Task run method. Creates a spaCy document.

        Args:
            - text (unicode, optional): text to be processed

        Returns:
            - Doc: spaCy document
        """
        doc = self.nlp(text)

        return doc


class SpacyTagger(Task):
    """
    Task for returning tagger from a spaCy pipeline.

    Args:
        - nlp (spaCy text processing pipeline, optional): a custom spaCy text
            processing pipeline
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, nlp=None, **kwargs):
        self.nlp = nlp
        super().__init__(**kwargs)

    @defaults_from_attrs("nlp")
    def run(self, nlp=None):
        """
        Task run method. Returns tagger component of spaCy pipeline.

        Args:
            - nlp (spaCy text processing pipeline, optional): a custom spaCy text
                processing pipeline, must be provided if not
                specified in construction

        Returns:
            - Tagger: spaCy Tagger object

        """
        if nlp is None:
            raise ValueError("A spaCy pipeline must be provided")

        return nlp.tagger


class SpacyParser(Task):
    """
    Task for returning parser from a spaCy pipeline.

    Args:
        - nlp (spaCy text processing pipeline, optional): a custom spaCy text
            processing pipeline
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, nlp=None, **kwargs):
        self.nlp = nlp
        super().__init__(**kwargs)

    @defaults_from_attrs("nlp")
    def run(self, nlp=None):
        """
        Task run method. Returns parser component of spaCy pipeline.

        Args:
            - nlp (spaCy text processing pipeline, optional): a custom spaCy text
                processing pipeline, must be provided if not
                specified in construction

        Returns:
            - Parser: spaCy Parser object

        """
        if nlp is None:
            raise ValueError("A spaCy pipeline must be provided")

        return nlp.parser


class SpacyNER(Task):
    """
    Task for returning named entity recognizer from a spaCy pipeline.

    Args:
        - nlp (spaCy text processing pipeline, optional): a custom spaCy text
            processing pipeline
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, nlp=None, **kwargs):
        self.nlp = nlp
        super().__init__(**kwargs)

    @defaults_from_attrs("nlp")
    def run(self, nlp=None):
        """
        Task run method. Returns named entity recognition component of spaCy pipeline.

        Args:
            - nlp (spaCy text processing pipeline, optional): a custom spaCy text
                processing pipeline, must be provided if not
                specified in construction

        Returns:
            - NER: spaCy NER object

        """
        if nlp is None:
            raise ValueError("A spaCy pipeline must be provided")

        return nlp.entity


class SpacyComponent(Task):
    """
    Task for returning named component from a spaCy pipeline.

    Args:
        - component_name (str, optional): name of spaCy pipeline component to return,
            must be provided during construction or run time
        - nlp (spaCy text processing pipeline, optional): a custom spaCy text
            processing pipeline
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, component_name: str = "", nlp=None, **kwargs):
        self.component_name = component_name
        self.nlp = nlp
        super().__init__(**kwargs)

    @defaults_from_attrs("component_name", "nlp")
    def run(self, component_name: str, nlp=None):
        """
        Task run method. Returns named component of spaCy pipeline.

        Args:
            - component_name (str, optional): name of spaCy pipeline component to return,
                must be provided during construction or run time
            - nlp (spaCy text processing pipeline, optional): a custom spaCy text
                processing pipeline, must be provided if not
                specified in construction

        Returns:
            - Component: spaCy pipeline component object

        """

        if nlp is None:
            raise ValueError("A spaCy pipeline must be provided")

        # iterate through pipeline to find object
        for name, component in nlp.pipeline:
            if name == component_name:
                return component

        raise ValueError("Pipeline component %s not found" % component_name)
