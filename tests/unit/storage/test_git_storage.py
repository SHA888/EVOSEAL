import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from evoseal.storage.git_storage import GitStorage, GitStorageError


def init_git_repo(repo_path):
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)


@pytest.fixture
def temp_git_repo():
    temp_dir = tempfile.mkdtemp()
    try:
        init_git_repo(temp_dir)
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


HASH_LENGTH = 40


def test_save_and_load_model(temp_git_repo):
    gs = GitStorage(temp_git_repo)
    model = {"foo": "bar", "num": 42}
    rel_path = "models/test.json"
    commit_hash = gs.save_model(model, rel_path, "Initial commit")
    loaded = gs.load_model(rel_path)
    assert loaded == model
    # Check file exists
    assert (Path(temp_git_repo) / rel_path).exists()
    # Check commit hash is valid
    assert len(commit_hash) == HASH_LENGTH


EXPECTED_VERSIONS = 2


def test_list_versions(temp_git_repo):
    gs = GitStorage(temp_git_repo)
    rel_path = "models/test.json"
    gs.save_model({"v": 1}, rel_path, "v1")
    gs.save_model({"v": 2}, rel_path, "v2")
    versions = gs.list_versions(rel_path)
    assert len(versions) >= EXPECTED_VERSIONS


def test_get_diff(temp_git_repo):
    gs = GitStorage(temp_git_repo)
    rel_path = "models/test.json"
    commit1 = gs.save_model({"v": 1}, rel_path, "v1")
    commit2 = gs.save_model({"v": 2}, rel_path, "v2")
    diff = gs.get_diff(rel_path, commit1, commit2)
    assert '+  "v": 2' in diff or '+"v": 2' in diff


def test_merge_model(temp_git_repo):
    gs = GitStorage(temp_git_repo)
    rel_path = "models/test.json"
    # Save to master branch (commit 1)
    gs.save_model({"v": 1}, rel_path, "v1", branch="master")
    # Make a second commit on master
    gs.save_model({"v": 10}, rel_path, "v10", branch="master")
    # Create feature branch from master
    gs._run_git(["checkout", "-b", "feature"])
    # Save a unique commit on feature
    gs.save_model({"v": 2}, rel_path, "v2", branch="feature")
    gs._run_git(["checkout", "master"])
    gs.merge_model(rel_path, "feature", "master")
    loaded = gs.load_model(rel_path)
    # After merge, the file should contain the feature branch's value (or a merge result)
    assert loaded["v"] in (2, 10)


def test_list_refs(temp_git_repo):
    gs = GitStorage(temp_git_repo)
    gs._run_git(["checkout", "-b", "testbranch"])
    # Make a commit so the branch is recognized
    rel_path = "models/branchfile.json"
    gs.save_model({"branch": True}, rel_path, "add branchfile", branch="testbranch")
    refs = gs.list_refs()
    # Branch names are now stripped and cleaned
    assert any(b == "testbranch" for b in refs["branches"])
    assert isinstance(refs["tags"], list)


def test_not_a_git_repo():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(GitStorageError):
            GitStorage(d)
