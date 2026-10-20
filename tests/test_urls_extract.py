from pathlib import Path

import pytest

from nepali_resource_audit.extract import extract_file, extract_markdown, license_hints
from nepali_resource_audit.urls import canonicalize, classify, lookup_target

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("a,b", [
    ("https://github.com/Foo/Bar", "http://www.github.com/foo/bar.git"),
    ("https://github.com/foo/bar/tree/main/data", "https://github.com/foo/bar/"),
    ("https://huggingface.co/datasets/Org/Name", "https://huggingface.co/datasets/org/name/viewer/default/train"),
    ("https://www.kaggle.com/user/slug", "https://www.kaggle.com/datasets/User/Slug?utm_source=x"),
    ("https://arxiv.org/abs/2401.00001v3", "https://arxiv.org/pdf/2401.00001.pdf"),
    ("https://dx.doi.org/10.1/ABC", "https://doi.org/10.1/abc"),
    ("https://example.org/a/?utm_campaign=z", "https://www.example.org/a"),
])
def test_same_resource_same_key(a, b):
    assert canonicalize(a) == canonicalize(b)


@pytest.mark.parametrize("a,b", [
    ("https://github.com/foo/bar", "https://github.com/foo/baz"),
    ("https://huggingface.co/datasets/org/name", "https://huggingface.co/org/name"),  # dataset vs model
    ("https://kaggle.com/competitions/x", "https://kaggle.com/datasets/x/x"),
    ("https://example.org/a?id=1", "https://example.org/a?id=2"),
])
def test_different_resources_different_keys(a, b):
    assert canonicalize(a) != canonicalize(b)


def test_classify_and_lookup_target():
    assert classify(canonicalize("https://github.com/a/b")) == "github-repo"
    assert classify(canonicalize("https://huggingface.co/datasets/a/b")) == "huggingface-dataset"
    assert classify(canonicalize("https://huggingface.co/a/b")) == "huggingface-model"
    assert classify(canonicalize("https://kaggle.com/a/b")) == "kaggle-dataset"
    assert classify(canonicalize("https://arxiv.org/abs/2401.00001")) == "paper-or-archive"
    assert classify(canonicalize("https://openslr.org/54/")) == "openslr"
    assert lookup_target("github.com/a/b") == ("github", "a/b")
    assert lookup_target("huggingface.co/datasets/a/b") == ("hf-dataset", "a/b")
    assert lookup_target("kaggle.com/datasets/a/b") is None


@pytest.mark.parametrize("text,expected", [
    ("License: CC BY-SA 4.0", ["CC-BY-SA"]),
    ("CC-BY-NC-SA", ["CC-BY-NC-SA"]),
    ("MIT licensed", ["MIT"]),
    ("Apache 2.0", ["Apache-2.0"]),
    ("released as public domain", ["public-domain"]),
    ("see https://github.com/mit-lab/thing", []),  # URL text must not count as a licence
    ("CC0", ["CC0-1.0"]),
    ("just a description", []),
])
def test_license_hints(text, expected):
    assert license_hints(text) == expected


def test_extract_fixture_a():
    ms = extract_file(FIX / "list_a.md", "A")
    assert len(ms) == 4  # code block link ignored
    by = {m.canonical: m for m in ms}
    news = by["huggingface.co/datasets/exampleorg/news-corpus"]
    assert news.name == "Example News Corpus" and news.verified_mark and news.license_hints == ["CC-BY-SA"]
    assert news.section == "Text corpora"
    assert by["github.com/exampleorg/speech-set"].license_hints == ["MIT"]
    assert by["arxiv.org/abs/2401.00001"].name == "Example Benchmark paper"  # table first cell


def test_badges_and_bare_urls():
    ms = extract_markdown("![b](https://img.shields.io/x.svg)\n* see https://example.org/x.\n", "S")
    assert [m.canonical for m in ms] == ["example.org/x"]


@pytest.mark.parametrize("url", ["https://huggingface.co", "https://huggingface.co/", "https://kaggle.com",
                                 "https://github.com", "https://github.com/onlyowner", "https://arxiv.org/",
                                 "https://huggingface.co/datasets"])
def test_bare_hosts_and_short_paths_do_not_crash(url):
    c = canonicalize(url)
    assert isinstance(classify(c), str)
    assert lookup_target(c) is None
