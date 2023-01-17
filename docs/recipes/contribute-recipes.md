---
description: Share your Prefect solution recipes with the Prefect Community.
tags:
    - contributing
    - recipes
    - examples
    - use cases
---

# Share Your Solutions with the Prefect Community

[Prefect recipes](https://github.com/PrefectHQ/prefect-recipes) provide a vital cookbook from which Prefect users can find helpful code examples and, when appropriate, common steps to Prefect solutions for specific use cases. 

We love submissions for recipes from anyone who has an example that another Prefect user can follow to achieve a common Prefect solution.

## What is a recipe?

A Prefect recipe is like a cookbook recipe: it tells you what you need &mdash; the ingredients &mdash; and some basic steps, but assumes you can put the pieces together. Think of the Hello Fresh meal experience, but for dataflows.

A tutorial, on the other hand, is Julia Child holding your hand through the entire cooking process: explaining each ingredient and procedure, demonstrating best practices, pointing out potential problems, and generally making sure you can’t stray from the happy path to a delicious meal.

We love Julia, and we love tutorials. But we don’t expect that a Prefect recipe should handhold users through every step and possible contingency of a solution. A recipe can start from an expectation of more expertise and problem-solving ability on the part of the reader.

To see an example of a high quality recipe, check out **[Serverless with AWS Chalice](https://github.com/PrefectHQ/prefect-recipes/tree/main/flows-advanced/serverless)**. This recipe includes all of the elements we like to see.

## What to do, explained in a brief recipe

Here’s our brief recipe for creating a useful recipe:

1. Clone the [Prefect Recipes repo](https://github.com/PrefectHQ/prefect-recipes) and create a branch.
2. [Write your code](#what-are-the-common-ingredients-of-a-good-recipe).
3. Write a [README](#what-are-some-tips-for-a-good-recipe-readme).
4. Include a dependencies file, if applicable.
5. Add your recipes where you think it fits in the repo. If you’re at all unsure, just add it anywhere and create a PR. A Prefect maintainer will help you find a good place for the recipe.  
6. Make a PR to the repo

That’s really it! 

## What makes a good recipe?

Any example that helps a Prefect user bake a great dataflow solution!

## What are the common ingredients of a good recipe?

Every recipe is useful.

Showing the cool example of using Prefect is the most important part. Show off. Other users can adapt the recipe to their needs. 

Some best practice for creating useful Prefect recipes:

- Make it easy to follow: We find that useful recipes are based on a example code that a user can follow.
- Include a README or code comments: A simple explanation providing context on how to use the example code is useful, but not required. A good README can set a recipe apart, so we have some additional suggestions for README files below.
- Language/format: Sometimes the example code is a configuration file &mdash; think of a Dockerfile or Terraform file for configuring infrastructure.
- Include code examples: Share as much code as you can. Even boilerplate code like Dockerfiles or Terraform or Helm files are useful. Just *don’t share company secrets or IP*.
- Don't worry about generalizing your code: Aside from removing anything internal/secret, don’t worry about it! Other users will extrapolate their own unique solutions from your example.

## What are some tips for a good recipe README?

A thoughtful README can take a recipe from good to great. Here are some best practices that we’ve found make for a great recipe README:

- Provide a brief explanation of what your recipe demonstrates. This helps users determine quickly whether the recipe is relevant to their needs or answers their questions.
- List which files are included and what each is meant to do. Each explanation can contain only a few words.
- Describe any dependencies and prerequisites (in addition to any dependencies you include in a requirements file). This includes both libraries or modules and any services your recipes depends on.
- If steps are involved or there’s an order to do things, a simple list of steps is helpful.
- Bonus: troubleshooting steps you encountered to get here or tips where other users might get tripped up.

## Next steps

We hope you’ll feel comfortable sharing your Prefect solutions as Prefect recipes in the [prefect-recipes repo](https://github.com/PrefectHQ/prefect-recipes#contributions). Collaboration and knowledge sharing are defining attributes of our [Prefect Community](https://www.prefect.io/slack)! 

Have questions about sharing or using recipes? Reach out on our active [Prefect Slack Community](https://www.prefect.io/slack)!

Have a blog post, Discourse article, or tutorial you’d like to share as a recipe? All submissions are welcome. Clone the prefect-recipes repo, create a branch, add a link to your recipe to the README, and submit a PR. 

Happy engineering!