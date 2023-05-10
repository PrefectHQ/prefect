from prefect import flow


@flow
def my_favorite_function():
    print("What is your favorite number?")
    return 42


print(my_favorite_function())
