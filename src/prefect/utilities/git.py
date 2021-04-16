from tempfile import TemporaryDirectory
from typing import Any

from dulwich.index import build_index_from_tree
from dulwich.porcelain import clone


class TemporaryGitRepo:
    """
    Temporary cloning and interacting with a git repository

    Args;
        - git_clone_url (str): Url to git clone
        - branch_name (str, optional): branch name, if not specified and `tag` not specified,
            repo default branch will be used
        - tag (str, optional): tag name, if not specified and `branch_name` not specified,
            repo default branch will be used
        - clone_depth (int): the number of history revisions in cloning, defaults to 1
    """

    def __init__(
        self,
        git_clone_url: str,
        branch_name: str = None,
        tag: str = None,
        clone_depth: int = 1,
    ) -> None:
        if tag and branch_name:
            raise ValueError(
                "Either `tag` or `branch_name` can be specified, but not both"
            )
        self.git_clone_url = git_clone_url
        self.branch_name = branch_name
        self.tag = tag
        self.clone_depth = clone_depth

    def __enter__(self) -> "TemporaryGitRepo":
        self.temp_dir = TemporaryDirectory()
        self.repo = clone(
            source=self.git_clone_url, target=self.temp_dir.name, depth=self.clone_depth
        )
        if self.branch_name is not None or self.tag is not None:
            self.checkout_ref()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.temp_dir.cleanup()

    def checkout_ref(self) -> None:
        """
        Checkout a specific ref from the repo
        """
        build_index_from_tree(
            self.repo.path,
            self.repo.index_path(),
            self.repo.object_store,
            self.get_tree_id_for_branch_or_tag(),
        )

    def get_tree_id_for_branch_or_tag(self) -> str:
        """
        Gets the tree id for relevant branch or tag
        """
        if self.branch_name is not None:
            ref = f"refs/remotes/origin/{self.branch_name}".encode("utf-8")
        elif self.tag is not None:
            ref = f"refs/tags/{self.tag}".encode("utf-8")
        else:
            raise ValueError(
                "Either `tag` or `branch_name` must be specified to get a tree id"
            )
        return self.repo[self.repo.get_refs()[ref]].tree
