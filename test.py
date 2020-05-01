import pandas as pd
from prefect import task, Flow


# import graphviz
# print(graphviz.FORMATS)


@task()
def generate_data():
    return pd.DataFrame({"one": [1, 2, 3], "two": [4, 5, 6]})

@task()
def double_data(input_data):
    return input_data * 2


with Flow("test") as flow:
    initial_data = generate_data()
    two_x_data = double_data(initial_data)
    four_x_data = double_data(two_x_data)



flow.visualize(filename="test", format="tiff")
