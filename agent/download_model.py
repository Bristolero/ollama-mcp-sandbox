from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a Hugging Face model locally.")
    parser.add_argument(
        "--model-id",
        default="mistralai/Mistral-7B-Instruct-v0.3",
        help="Model repo id on Hugging Face.",
    )
    parser.add_argument(
        "--target-dir",
        default="models/mistral-7b-instruct-v0.3",
        help="Directory where the model files will be stored.",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded_path = snapshot_download(
        repo_id=args.model_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    print(f"Model downloaded to: {downloaded_path}")


if __name__ == "__main__":
    main()
