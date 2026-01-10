#!/bin/bash

set -x

# HuggingFace Env Var
# https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables
# prevent autodownload
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

set +x
