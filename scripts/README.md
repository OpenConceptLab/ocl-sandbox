# README

## Match Usage
```bash
# Basic usage with LLM evaluation
python match.py -t=[OCL-TOKEN] -i=./samples/test_llm.csv \
    --anthropic-api-key=[YOUR-KEY] \
    -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ \
    -e=https://api.dev.openconceptlab.org

# With debug mode and custom model
python match.py -t=[OCL-TOKEN] -i=./samples/test_llm.csv \
    --anthropic-api-key=[YOUR-KEY] \
    --model=claude-3-5-sonnet-20241022 \
    --debug \
    -o=./output/results_with_ai.csv

# With everything
python ./scripts/match.py \
    -t=[OCL-API-TOKEN] \
    -k=[ANTHROPIC-KEY] \
    --model=claude-3-5-sonnet-20241022 \
    --debug \
    -i=./samples/ciel_loinc_sample_1.csv \
    -r=/orgs/Regenstrief/sources/LOINC/2.71.21AA/ \
    -e=https://api.dev.openconceptlab.org \
    -n=5 \
    -v=2 \
    --correctmap=loinc_code \
    --filter-loinc-type=LOINC \
    --filter-fetch-factor=3 \
    -o=./output/ciel_loinc_sample_1_output_with_ai.csv
```
