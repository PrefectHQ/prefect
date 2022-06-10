from prefect import flow, task

map = task(lambda x: x + 1)
reduce = task(lambda x: sum(x))


@flow
def map_reduce():
    print(map(1).result())
    print(map(2).result())
    print(reduce([1, 2, 3]).result())
    print(reduce([4, 5, 6]).result())


if __name__ == "__main__":
    map_reduce()
