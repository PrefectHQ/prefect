#!/usr/bin/env python3
"""
Quick test to make sure flows with tasks work correctly.
"""

from prefect import flow, task

@task
def add_one(x):
    return x + 1

@task  
def multiply_by_two(x):
    return x * 2

@flow
def simple_math_flow():
    result1 = add_one(5)
    result2 = multiply_by_two(result1)
    return result2

if __name__ == "__main__":
    print("Testing flow with tasks...")
    result = simple_math_flow()
    print(f"✓ Flow completed successfully with result: {result}")