"""Rename the entry point in early AWS model artifacts that shadowed a framework package.

The first RF/SVM packages used code/sagemaker_inference.py. That filename shadows the
framework's installed sagemaker_inference package and prevents the endpoint from
booting. New pipeline runs already produce code/ids_inference.py; this utility repairs
only those first immutable artifacts before registering corrected package versions.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import tarfile


OLD_NAME = "code/sagemaker_inference.py"
NEW_NAME = "code/ids_inference.py"
EXPECTED = {"model.pkl", "preprocessor.joblib", "validation_metrics.json", OLD_NAME}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error("source and destination must differ")
    args.destination.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(args.source, "r:gz") as source:
        members = {member.name: member for member in source.getmembers() if member.isfile()}
        if set(members) != EXPECTED:
            raise ValueError(f"Unexpected artifact members: {sorted(members)}")
        with tarfile.open(args.destination, "w:gz") as destination:
            for name in sorted(members):
                body = source.extractfile(members[name])
                if body is None:
                    raise ValueError(f"Could not read {name}")
                data = body.read()
                target = NEW_NAME if name == OLD_NAME else name
                info = tarfile.TarInfo(target)
                info.size = len(data)
                info.mode = 0o644
                destination.addfile(info, io.BytesIO(data))
    print(args.destination)


if __name__ == "__main__":
    main()
