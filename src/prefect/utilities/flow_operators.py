import prefect
from prefect import Flow
from prefect.utilities import logging
"""
This module contains methods to combine multiple flows. It is a limited adaptation of networkx operators.

Copyright (C) 2004-2019, NetworkX Developers
Aric Hagberg <hagberg@lanl.gov>
Dan Schult <dschult@colgate.edu>
Pieter Swart <swart@lanl.gov>
All rights reserved.
"""

def disjoint_union(G: "Flow", H: "Flow", validate: bool = True) -> Flow:
    """
        Take all tasks and edges in flow G and H and makes a new disjointed flow.
        Duplicate parameters and tasks are given a new slug and name.  Using the 
        template `{flow.name}-{task.slug}`.

        This is useful in two cases:
        1. When two disparate flows can be run in one enviroment.
        2. When one flow is dependent on another flow with no data dependencies.

        Args:
            - G, H (Flow): flow 1 and flow 2  
            - validate (bool, optional): Default True. Whether or not to check the validity of the flow
                      

        Returns:
            - U (Flow): A new flow is created.
        """
    flow1 = G.copy()
    flow2 = H.copy()

    for task in flow2.tasks:

        fl1_tsk = flow1.get_tasks(task.name)

        # Check for duplicate names
        if len(fl1_tsk) > 0:

            duped_task = fl1_tsk[0]

            print(f"Duplicate task {duped_task}")

            task.name = f"{flow2.name}-{task.name}"
            task.slug = f"{flow2.name}-{task.slug}"

            duped_task.name = f"{flow1.name}-{duped_task.name}"
            duped_task.slug = f"{flow1.name}-{duped_task.slug}"

        flow1.add_task(task)


    for edge in flow2.edges:
        if edge not in flow1.edges:
            flow1.add_edge(
                upstream_task=edge.upstream_task,
                downstream_task=edge.downstream_task,
                key=edge.key,
                mapped=edge.mapped,
                validate=validate,
            )

    flow1.constants.update(flow2.constants or {})

    flow1._cache.clear()
    flow2._cache.clear()

    return flow1
