"""What a model can be, and every job a model can be assigned to.

Strings only, like `campaigns.registry`: this app knows the names of the jobs,
never the channel code that runs them. A job without its own assignment uses
the default of its kind.
"""

LLM = "llm"
IMAGE = "image"
VIDEO = "video"
EMBEDDING = "embedding"

KINDS = [
    (LLM, "Language model"),
    (IMAGE, "Image"),
    (VIDEO, "Video"),
    (EMBEDDING, "Embedding"),
]

# purpose -> (kind, label a person reads)
PURPOSES = {
    "default.llm": (LLM, "Default (LLM)"),
    "instagram.spark": (LLM, "Reel · Spark: three takes"),
    "instagram.hook": (LLM, "Reel · Hook"),
    "instagram.board": (LLM, "Reel · Board"),
}


def default_for(kind: str) -> str:
    return f"default.{kind}"


def label(purpose: str) -> str:
    return PURPOSES[purpose][1]
