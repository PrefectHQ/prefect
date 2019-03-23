---
sidebarDepth: 0
---

# Why Prefect?

## Negative engineering

Every piece of code has some purpose or objective that it seeks to achieve. We call that **positive engineering**.

However, in order to execute code in an automated way, we need to answer an enormous number of questions:

- when should it run?
- where should it run?
- what dependencies does it require?
- what inputs does it require?
- can it be paused and resumed seamlessly?
- what logs does it produce and how to access them?
- what outputs does it produce?
- where are outputs stored?
- what happens if it succeeds?
- what happens if it fails?
- what happens if it encounters an error?
- what happens if the computer it runs on crashes?
- under what circumstances should notifications be sent?
- can it be retried?
- when should it retry?
- can it be skipped?
- ...

Each question, taken individually, might be trivial, but complexity starts to emerge when we combine them. If we contemplate thousands of concurrent tasks running in distributed, possibly disjoint environments, the entire system breaks down.

We call this complexity **negative engineering**. It encompasses everything that needs to be done to ensure that positive engineering can run robustly. Focusing on negative engineering is critical because it ensures that code runs as intended. However, most engineers don't like building negative infrastructure because it's often orthagonal to the postive code they set out to write in the first place.

**Prefect is an automation framework for negative engineering.** Prefect's job is to make sure that no matter what your code is, or what environment it's deployed to, it gets executed in a controlled manner that satisfies all of these negative engineering requirements.


## "This should be easy"

Each aspect of negative engineering seems simple. How hard could it be to trap an error, store logs, retry, or create an execution endpoint? Unsurprisingly, the most common thing we hear from users is: "This should be easy."

And they're right: it should be.

But negative engineering requirements compound. The more things the positive code does, the more complex the negative engineering challenge becomes.

The trend among workflow systems is to tackle this complexity by exposing it to the user. This has led to a proliferation of configuration files and obscure data structures that "only an engineer could love."

Unlike other tools, Prefect doesn't require you to know (or care) about every single automation detail. Prefect has a common-sense default for everything, informed by extensive user research. If you just want to run a function at 8am every day, then that's the only bit of information you need to provide. Prefect will handle everything else. On the other hand, if you ARE the type of person who loves to introspect a complex DAG data structure, it's got you covered. Prefect is the most complete automation framework available.
