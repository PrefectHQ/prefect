## Why Blocks

Today there are many low-code data integration tools - “connectors” to popular applications. These tools are great for setting up connections to common systems, but they’re not code-first, or even code-second. It can be complex to do anything custom with these tools.

**Low-code connectors often come in two kinds - sources and destinations.** That’s great for straightforward ELT pipelines, but modern dataflows don’t just extract and load data. They write intermediate outputs, call out to web services, transform data, train models, set up job-specific infrastructure, and much more.

Prefect’s [Blocks](/concepts/blocks/) offer the advantages of low-code connectors with a first class experience in code. The code first approach means Blocks are connectors for code that can go beyond source and destination.

## Why Create Custom Block Types

Prefect offers a wide variety of block types straight out of the box. However, it doesn't limit you there. You can easily create custom block types to meet the specific needs of your project by inheriting from the base Block class. After all, at their core, blocks are nothing more than your friendly neighborhood Python class.

With custom block types, as your data platform evolves, your building blocks don’t have to be replaced. Instead, they can gain new capabilities.

### 1. Inherit from Block Class and Add Attributes

```python
class GitHubIssues(Block):
    """
    Interact with GitHub's API to get issues of a given repository.
    Get the most recently commented issue.

    Attributes:
        username (str): The username of the repository's owner.
        repo (str): The name of the repository.
        state (str): The state of the issues to return. Can be either 'open', 'closed', or 'all'. Default is 'open'.
    """
    username: str
    repo: str
    state: str = 'open'
```

## 2. Add Methods (aka: Capabilities)

Add an underscore class before names of helper methods.
```python
    def _construct_url(self) -> str:
        return f"https://api.github.com/repos/{self.username}/{self.repo}/issues?state={self.state}"

    def get_issues(self) -> list:
        url = self._construct_url()
        response = requests.get(url)
        response.raise_for_status()  # Will raise an exception if the status code is not 200
        return response.json()
    
    def get_most_recently_commented_issue(self) -> dict:
        issues = self.get_issues()
        most_recent_issue = max(issues, key=lambda issue: datetime.fromisoformat(issue['updated_at'].rstrip("Z")))
        return most_recent_issue
```

### 3. Add class-level details:

Provide some details about your block. These details include the block type name, logo URL, block schema capabilities, and any attributes that your block might have.

```python
    username: str
    repo: str
    state: str = 'open'
    _block_type_name = "GitHub Issues"
    _block_schema_capabilities = ["get_issues", "get_most_recently_commented_issue"]
    _logo_url = "https://static.vecteezy.com/system/resources/previews/014/802/399/original/daily-flow-issues-organization-realization-flat-color-icon-icon-banner-template-free-vector.jpg"
```

### 4. Register Your Block

```bash
prefect block register --file custom_block.py
```

## Next Steps

- Consider open sourcing your custom block type, use our collections template
For more advanced block features, checkout blocks from our collections catalogue, the [S3Bucket](https://github.com/PrefectHQ/prefect-aws/blob/main/prefect_aws/s3.py#L236) Block is a good place to start.