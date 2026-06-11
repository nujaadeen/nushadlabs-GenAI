# nushadlabs-GenAI

A hands-on repository for demonstrating and validating core **Generative AI** concepts through interactive Jupyter notebooks.

## Purpose

This repo is a personal lab for exploring how modern LLMs and generative models work under the hood — from tokenization to training — with working code that validates each concept.

## Notebooks

| Notebook | Concept | Description |
|----------|---------|-------------|
| [tokenizer.ipynb](tokenizer.ipynb) | Tokenization | GPT-2 BPE tokenizer usage, vocab inspection, and training a custom BPE tokenizer from scratch |

## Concepts Covered

- **Tokenization** — How text is converted to token IDs using Byte Pair Encoding (BPE)
- **Pretrained Tokenizers** — Loading and using Hugging Face tokenizers (`GPT2Tokenizer`, `GPT2TokenizerFast`)
- **Tokenizer Internals** — Understanding `vocab.json` and `merges.txt`
- **Custom Tokenizer Training** — Training a BPE tokenizer from scratch with the `tokenizers` library

## Setup

```bash
pip install transformers tokenizers
```

## Stack

- Python 3.x
- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
- [Hugging Face Tokenizers](https://huggingface.co/docs/tokenizers)
- Jupyter Notebook
