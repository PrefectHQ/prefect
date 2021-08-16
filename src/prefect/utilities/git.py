from tempfile import TemporaryDirectory
from typing import Any


class TemporaryGitRepo:
    """
    Temporary cloning and interacting with a git repository

    Args:
        - git_clone_url (str): Url to git clone
        - branch_name (str, optional): branch name, if not specified and `tag` not specified,
            repo default branch latest commit will be used
        - tag (str, optional): tag name, if not specified and `branch_name` not specified,
            repo default branch latest commit will be used
        - commit (str, optional): a commit SHA-1 value, if not specified and `branch_name`
            and `tag` not specified, repo default branch latest commit will be used
        - clone_depth (int): the number of history revisions in cloning, defaults to 1
    """

    def __init__(
        self,
        git_clone_url: str,
        branch_name: str = None,
        tag: str = None,
        commit: str = None,
        clone_depth: int = 1,
    ) -> None:
        if tag and branch_name:
            raise ValueError(
                "Either `tag` or `branch_name` can be specified, but not both"
            )
        self.git_clone_url = git_clone_url
        self.branch_name = branch_name
        self.tag = tag
        self.commit = commit
        self.clone_depth = clone_depth

    def __enter__(self) -> "TemporaryGitRepo":
        try:
            from dulwich.porcelain import clone
        except ImportError as exc:
            raise ImportError(
                "Unable to import dulwich, please ensure you have installed the git extra"
            ) from exc

        self.temp_dir = TemporaryDirectory()
        self.repo = clone(
            source=self.git_clone_url, target=self.temp_dir.name, depth=self.clone_depth
        )
        if self.branch_name is not None or self.tag is not None:
            self.checkout_ref()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # 'close' the repo so files are not still in use
        self.repo.close()
        # then remove the temporary files
        self.temp_dir.cleanup()

    def checkout_ref(self) -> None:
        """
        Checkout a specific ref from the repo
        """
        try:
            from dulwich.index import build_index_from_tree
        except ImportError as exc:
            raise ImportError(
                "Unable to import dulwich, please ensure you have installed the git extra"
            ) from exc

        build_index_from_tree(
            self.repo.path,
            self.repo.index_path(),
            self.repo.object_store,
            self.get_tree_id_for_branch_or_tag(),
        )

    @property
    def branch_or_tag_ref(self) -> bytes:
        """
        Get the branch or tag ref for the current repo
        """
        if self.branch_name is not None:
            return f"refs/remotes/origin/{self.branch_name}".encode("utf-8")
        elif self.tag is not None:
            return f"refs/tags/{self.tag}".encode("utf-8")
        raise ValueError(
            "Either `tag` or `branch_name` must be specified to get a tree id"
        )

    def get_tree_id_for_branch_or_tag(self) -> str:
        """
        Gets the tree id for relevant branch or tag
        """
        if self.commit is not None:
            return self.repo[self.commit.encode("utf-8")]
        return self.repo[self.repo.get_refs()[self.branch_or_tag_ref]].tree
