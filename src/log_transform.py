from pydantic import BaseModel  # used to define schema
from typing import List
import math

class LogTransformation(BaseModel):
    base: float = math.e  
    offset: float = 1.0   # add to each value before applying log to prevent nonpositives 

def log_transform(data: List[float], config: LogTransformation) -> List[float]:
    result = []

    for val in data:
        if val + config.offset <= 0:
            raise ValueError("Logarithms are undefined for ≤ 0")

        log_value = math.log(val + config.offset, config.base)  # formula for log transformation
        result.append(log_value)  # store result

    return result

def log_pipeline():
    data = [1, 10, 100, 1000]

    config = LogTransformation(base=10, offset=1)

    result = log_transform(data, config)
    print("Log Transformed Data:", result)


if __name__ == "__main__":
    log_pipeline()