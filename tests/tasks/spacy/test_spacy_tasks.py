from unittest.mock import MagicMock, Mock

import pytest
import spacy

from prefect.tasks.spacy.spacy_tasks import (
    SpacyComponent,
    SpacyNER,
    SpacyNLP,
    SpacyParser,
    SpacyTagger,
)


class TestSpacyNLP:
    def test_initialization(self):
        task = SpacyNLP(text="This is some text", nlp=spacy.blank("en"))
        assert task.text == "This is some text"

    def test_load_nlp_model(self):
        spacy.cli.download("en_core_web_sm")
        task = SpacyNLP(
            text="This is some text", spacy_model_name="en_core_web_sm"
        )
        assert task.nlp is not None

    def test_bad_model_raises_error(self):
        with pytest.raises(ValueError, match="not_a_spacy_model"):
            task = SpacyNLP(
                text="This is some text", spacy_model_name="not_a_spacy_model"
            )

    def test_text_passed_to_run(self):
        nlp = MagicMock()
        task = SpacyNLP(text="This is some text", nlp=nlp)
        task.run()
        assert nlp.call_args[0][0] == "This is some text"


class TestSpacyTagger:
    def test_initialization(self):
        task = SpacyTagger()
        assert task.nlp is None

    def test_get_tagger(self):
        mock = Mock()
        mock.tagger = "tagger"
        task = SpacyTagger(nlp=mock)
        tagger = task.run()
        assert tagger == "tagger"

    def test_nlp_model_provided(self):
        task = SpacyTagger()
        with pytest.raises(ValueError, match="A spaCy pipeline must be provided"):
            task.run()


class TestSpacyParser:
    def test_initialization(self):
        task = SpacyParser()
        assert task.nlp is None

    def test_get_parser(self):
        mock = Mock()
        mock.parser = "parser"
        task = SpacyParser(nlp=mock)
        parser = task.run()
        assert parser == "parser"

    def test_nlp_model_provided(self):
        task = SpacyParser()
        with pytest.raises(ValueError, match="A spaCy pipeline must be provided"):
            task.run()


class TestSpacyNER:
    def test_initialization(self):
        task = SpacyNER()
        assert task.nlp is None

    def test_get_ner(self):
        mock = Mock()
        mock.entity = "entity"
        task = SpacyNER(nlp=mock)
        ner = task.run()
        assert ner == "entity"

    def test_nlp_model_provided(self):
        task = SpacyNER()
        with pytest.raises(ValueError, match="A spaCy pipeline must be provided"):
            task.run()


class TestSpacyComponent:
    def test_initialization(self):
        task = SpacyComponent()
        assert task.component_name == ""

    def test_get_component(self):
        mock = Mock()
        mock.pipeline = [("component1", 1), ("component2", 2)]
        task = SpacyComponent(component_name="component2", nlp=mock)
        component = task.run()
        assert component == 2

    def test_nlp_model_provided(self):
        task = SpacyComponent()
        with pytest.raises(ValueError, match="A spaCy pipeline must be provided"):
            task.run()
