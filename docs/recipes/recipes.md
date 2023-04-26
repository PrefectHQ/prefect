---
description: Prefect Recipes provide extensible examples for common Prefect use cases.
tags:
    - recipes
    - best practices
    - examples
hide:
  - toc
---

# Prefect Recipes

[Prefect recipes](https://github.com/PrefectHQ/prefect-recipes) are common, extensible examples for setting up Prefect in your execution environment with ready-made ingredients such as Dockerfiles, Terraform files, and GitHub Actions.

Recipes are useful when you are looking for tutorials on how to deploy an agent, use event-driven flows, set up unit testing, and more.

The following are Prefect recipes specific to Prefect 2. You can find a full repository of recipes at [https://github.com/PrefectHQ/prefect-recipes](https://github.com/PrefectHQ/prefect-recipes) and additional recipes at [Prefect Discourse](https://discourse.prefect.io/).

## Recipe catalog

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div class="recipe-grid">
{% for collection in collections %}
    <div class="recipe-item">
        <div class="recipe-title">
            <a href="{{ collection['recipeUrl'] }}">
                <h3 style="margin: 0">{{collection['recipeName']}}</h3>
            </a>
        </div>
        <div class="recipe-desc">
            <p>
                {{ collection["description"] }}
            </p>
        </div>
        <div class="recipe-details">
            <p>
                Maintained by <a href="{{ collection["authorUrl"] }}">{{ collection["author"] }}</a>
            </p>
            <p>
                This recipe uses:
            </p>
            <p>
                {% for icon in collection['iconUrl'] %}
                    <img src="{{ icon }}" >
                {% endfor %}
            </p>
        </div>
    </div>
{% endfor %}
</div >

## Contributing recipes

We're always looking for new recipe contributions! See the [Prefect Recipes](https://github.com/PrefectHQ/prefect-recipes#contributing--swag-) repository for details on how you can add your Prefect recipe, share best practices with fellow Prefect users, and earn some swag. 

[Prefect recipes](https://github.com/PrefectHQ/prefect-recipes) provide a vital cookbook where users can find helpful code examples and, when appropriate, common steps for specific Prefect use cases.

We love recipes from anyone who has example code that another Prefect user can benefit from (e.g. a Prefect flow that loads data into Snowflake).

Have a blog post, Discourse article, or tutorial you’d like to share as a recipe? All submissions are welcome. Clone the prefect-recipes repo, create a branch, add a link to your recipe to the README, and submit a PR. Have more questions? Read on.

## What is a recipe?

A Prefect recipe is like a cookbook recipe: it tells you what you need &mdash; the ingredients &mdash; and some basic steps, but assumes you can put the pieces together. Think of the Hello Fresh meal experience, but for dataflows.

A tutorial, on the other hand, is Julia Child holding your hand through the entire cooking process: explaining each ingredient and procedure, demonstrating best practices, pointing out potential problems, and generally making sure you can’t stray from the happy path to a delicious meal.

We love Julia, and we love tutorials. But we don’t expect that a Prefect recipe should handhold users through every step and possible contingency of a solution. A recipe can start from an expectation of more expertise and problem-solving ability on the part of the reader.

To see an example of a high quality recipe, check out **[Serverless with AWS Chalice](https://github.com/PrefectHQ/prefect-recipes/tree/main/flows-advanced/serverless)**. This recipe includes all of the elements we like to see.

## Steps to add your recipe

Here’s our guide to creating a recipe:

<div class="terminal">
```bash
# Clone the repository
git clone git@github.com:PrefectHQ/prefect-recipes.git
cd prefect-recipes

# Create and checkout a new branch
git checkout -b new_recipe_branch_name
```
</div>

1. [Add your recipe](#what-are-the-common-ingredients-of-a-good-recipe). Your code may simply be a copy/paste of a single Python file or an entire folder. Unsure of where to add your file or folder? Just add under the `flows-advanced/` folder. A Prefect Recipes maintainer will help you find the best place for your recipe. Just want to direct others to a project you made, whether it be a repo or a blogpost? Simply link to it in the [Prefect Recipes README](https://github.com/PrefectHQ/prefect-recipes#readme)!
2. (Optional) Write a [README](#what-are-some-tips-for-a-good-recipe-readme).
3. Include a dependencies file, if applicable.
4. Push your code and make a PR to the repository.

That’s it! 

## What makes a good recipe?

Every recipe is useful, as other Prefect users can adapt the recipe to their needs. Particularly good ones help a Prefect user bake a great dataflow solution! Take a look at the [prefect-recipes repo](https://github.com/PrefectHQ/prefect-recipes) to see some examples.

## What are the common ingredients of a good recipe?

- Easy to understand: Can a user easily follow your recipe? Would a README or code comments help? A simple explanation providing context on how to use the example code is useful, but not required. A good README can set a recipe apart, so we have some additional suggestions for README files below.
- Code and more: Sometimes a use case is best represented in Python code or shell scripts. Sometimes a configuration file is the most important artifact &mdash; think of a Dockerfile or Terraform file for configuring infrastructure.
- All-inclusive: Share as much code as you can. Even boilerplate code like Dockerfiles or Terraform or Helm files are useful. Just *don’t share company secrets or IP*.
- Specific: Don't worry about generalizing your code, aside from removing anything internal/secret! Other users will extrapolate their own unique solutions from your example.

## What are some tips for a good recipe README?

A thoughtful README can take a recipe from good to great. Here are some best practices that we’ve found make for a great recipe README:

- Provide a brief explanation of what your recipe demonstrates. This helps users determine quickly whether the recipe is relevant to their needs or answers their questions.
- List which files are included and what each is meant to do. Each explanation can contain only a few words.
- Describe any dependencies and prerequisites (in addition to any dependencies you include in a requirements file). This includes both libraries or modules and any services your recipes depends on.
- If steps are involved or there’s an order to do things, a simple list of steps is helpful.
- Bonus: troubleshooting steps you encountered to get here or tips where other users might get tripped up.

## Next steps

We hope you’ll feel comfortable sharing your Prefect solutions as recipes in the [prefect-recipes repo](https://github.com/PrefectHQ/prefect-recipes#contributions). Collaboration and knowledge sharing are defining attributes of our [Prefect Community](https://www.prefect.io/slack)! 

Have questions about sharing or using recipes? Reach out on our active [Prefect Slack Community](https://www.prefect.io/slack)!

Happy engineering!