# Medical Term Cross-Encoder

This module demonstrates a simple cross-encoder implementation for ranking medical terminology based on semantic similarity. It uses the Hugging Face Transformers library with a pre-trained cross-encoder model to rank LOINC medical terms against input text.

## Overview

The cross-encoder works by comparing a query text against a pool of candidate terms (in this case, a sample set of LOINC lab test codes and their descriptions) and ranking them by similarity. 

Our primary goal for introducing a cross-encoder:
- Ensure that scores are stable and reproducible even if the data store (i.e. Elasticsearch) is updated
- Combine candidates from multiple search methods (e.g. linearization, semantic searchy, cross-reference lookups) into a single ranked list

## Requirements

The following dependencies are required:
- transformers (>=4.41.0)
- torch (>=2.0.0)
- pandas (>=2.0.0)
- tqdm (>=4.65.0)

## Usage

### Basic Usage

```python
from cross_encode import MedicalTermRanker, candidate_pool

# Initialize the ranker with the default LOINC candidate pool
ranker = MedicalTermRanker(candidate_pool)

# Rank terms for a specific description
description = "blood glucose measurement"
ranked_results = ranker.rank_terms(description)

# Display the results
ranker.print_ranked_results(ranked_results)
```

## Model Details

The implementation uses the `cross-encoder/ms-marco-MiniLM-L-6-v2` model from Hugging Face, which has been fine-tuned for semantic similarity tasks. The model runs inference on either GPU (if available) or CPU.

## Customization

You can customize the candidate pool by modifying the `candidate_pool` list in the `cross_encode.py` file or by passing your own list to the `MedicalTermRanker` constructor:

```python
custom_candidates = [
    ("code1", "Description 1"),
    ("code2", "Description 2"),
    # ...
]
ranker = MedicalTermRanker(custom_candidates)
```

## Performance Considerations

- The ranking process uses tqdm to display progress for larger candidate pools
- GPU acceleration significantly improves performance for large batches
- Deterministic settings are enabled for better reproducibility
