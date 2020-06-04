import prefect


def disjoint_union(G: "Flow", H: "Flow", validate: bool = True) -> None:
    """
        Take all tasks and edges in another flow and makes a disjointed flow.
        Duplicate parameters and tasks are given a new slug and name.  Using the 
        template `{flow.name}-{task.slug}`.

        This is useful in two cases:
        1. When two disparate flows can be run in one enviroment.
        2. When one flow is dependent on another flow with no data dependencies.

        Args:
            - flow (Flow): A flow which is used to update this flow
            - validate (bool, optional): Default True. Whether or not to check the validity of the flow
                      

        Returns:
            - None
        """

    for task in flow.tasks:

        fl1_tsk = self.get_tasks(task.name)

        # Check for duplicate names
        if len(fl1_tsk) > 0:

            duped_task = fl1_tsk[0]

            print(f"Duplicate task {duped_task}")

            task.name = f"{flow.name}-{task.name}"
            task.slug = f"{flow.name}-{task.slug}"

            duped_task.name = f"{self.name}-{duped_task.name}"
            duped_task.slug = f"{self.name}-{duped_task.slug}"

        self.add_task(task)

    for edge in flow.edges:
        if edge not in self.edges:
            self.add_edge(
                upstream_task=edge.upstream_task,
                downstream_task=edge.downstream_task,
                key=edge.key,
                mapped=edge.mapped,
                validate=validate,
            )

    self.constants.update(flow.constants or {})
