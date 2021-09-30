# Orchestration

- no two programs are the same
    - we try to be as flexible as possible in how we govern when and how your code should execute
    - this is orchestration! the decision to run some code and adapt to what happens in a sensible and robust way

- flows and tasks are Prefect's basic unit of observability into how your code runs
- the state of flow or task run tells us everything we need to know to decide how to orchestrate a program
    - anything deeper would interfere with your flexibility to write your program the way you want
    - in "normal" operation, the description of state is straightforward: (PENDING-RUNNING-COMPLETE)
        - But of course, anything can happen!
        - It's easy to imagine that in a complex system, a flow or task will try to transition between states in all sorts of ways
        - examples?

- the job of the client is to simply try and run code--but check with orion before changing state!
    - governing this change of state (a state transition) is the domain of prefect orchestration
    - We believe all expectations of an orchestration system can happen within this abstraction
        - with all requests to change the execution state of a program centralized, the Orion instance becomes the sole source of truth:
            - current state of any run
            - global clock
            - etc
- This introduces a second responsibility of the client: knowing how to respond to Orion's instructions about how to proceed
    - because our surface area is limited to states, this is actually really intuitive:
        - everything's good to go: proceed!
        - transition to a different state instead
        - the system isn't ready yet, wait
        - stop executing entirely


## Orchestration Rules


## Policies and observability
