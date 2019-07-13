"""
This example walks through the basics of using Prefect tasks to run spaCy pipelines and interact with components.
"""

import spacy

from prefect import Flow
from prefect.tasks.spacy.spacy_tasks import (
    SpacyComponent,
    SpacyNER,
    SpacyNLP,
    SpacyParser,
    SpacyTagger,
)

# load a spacy language model
nlp = spacy.load("en_core_web_sm")

# add a custom component to language model
def custom_component(doc):
    # do something with document
    return doc


nlp.add_pipe(custom_component, name="custom")

# create flow for NLP
with Flow("Natural Language Processing") as flow:

    # create a spaCy doc from text, the equivalent of nlp('This is some text')
    doc = SpacyNLP(text="This is some text", nlp=nlp)

    # extract default components from language model pipeline
    tagger = SpacyTagger(nlp)
    parser = SpacyParser(nlp)
    ner = SpacyNER(nlp)

    # extract a custom component from language model pipeline by name
    custom_pipeline_component = SpacyComponent("custom")

flow.run()
