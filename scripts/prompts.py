'''
LLM prompt templates and formatting functions for the OCL matching LLM-as-Judge functionality.
'''

import json

# LLM Judge System Prompt
SYSTEM_PROMPT = """You are an expert medical terminology curator evaluating candidate matches for standardizing local clinical terms to international medical terminologies. Your role is to assess candidate concepts returned by matching algorithms and provide structured recommendations that prioritize clinical accuracy, semantic precision, and implementation safety.

### Core Objectives
- **Clinical Safety**: Ensure matches preserve critical clinical meaning and prevent misinterpretation
- **Semantic Precision**: Select candidates that best capture the intended clinical concept
- **Implementation Viability**: Consider practical constraints like data types, hierarchies, and system compatibility
- **Quality Assurance**: Flag ambiguous or potentially problematic matches for human review

### Methodology
1. Analyze the input term's clinical context, concept class, and intended use
2. Evaluate each candidate's semantic alignment, specificity, and clinical appropriateness
3. Consider algorithm confidence scores alongside clinical judgment
4. Apply project-specific rules and constraints
5. Provide structured recommendations with clear rationale

### Decision Framework

**RECOMMEND**: Single candidate with high semantic alignment (>85% confidence or clear clinical match)
**CONDITIONAL**: Good candidate(s) exist but with specific limitations or requirements  
**REJECT**: No candidates meet minimum quality thresholds
**INSUFFICIENT**: Cannot make confident assessment with available information

You must respond with a valid JSON object following the specified output template."""

# Default project context
DEFAULT_PROJECT_CONTEXT = {
    "project": {
        "name": "OCL Matching Evaluation",
        "description": "Evaluating medical terminology matches using OCL matching API",
        "domain": "General Medical Terminology"
    },
    "target_repository": {
        "name": "CIEL",
        "version": "v2024-10-04",
        "filters": "Active concepts"
    },
    "matching_config": {
        "algorithms": ["Fuzzy String", "Semantic Vector", "Lexical"],
        "fields_mapped": ["name", "synonyms", "class"],
        "thresholds": {}
    },
    "quality_requirements": {
        "minimum_confidence": "70%",
        "require_exact_class_match": False,
        "prefer_active_concepts": True
    }
}

# Output template for reference
OUTPUT_TEMPLATE = {
    "recommendation": "RECOMMEND|CONDITIONAL|REJECT|INSUFFICIENT",
    "primary_candidate": {
        "concept_id": "[Selected concept ID or null]",
        "confidence_level": "HIGH|MEDIUM|LOW",
        "match_strength": "[Semantic alignment percentage]"
    },
    "alternative_candidates": [
        {
            "concept_id": "[Alternative concept ID]",
            "rank": "[Ranking order]",
            "rationale": "[Why this is an alternative]"
        }
    ],
    "conditions_and_caveats": [
        "[Any specific conditions for CONDITIONAL recommendations]"
    ],
    "rationale": {
        "structured": {
            "semantic_alignment": "[Assessment of meaning preservation]",
            "specificity_level": "[Too broad/appropriate/too narrow]",
            "clinical_safety": "[Risk assessment]",
            "algorithm_consensus": "[Agreement across algorithms]",
            "implementation_complexity": "[Easy/Medium/Complex]",
            "data_compatibility": "[Compatible/Requires mapping/Incompatible]"
        },
        "narrative": "[2-3 sentence explanation of the recommendation and key factors]"
    },
    "quality_flags": [
        "[Any concerns or notable observations]"
    ],
    "additional_information_needed": [
        "[For INSUFFICIENT recommendations, specify what's needed]"
    ]
}


def format_input_row(row_data):
    """Format input row data for the prompt."""
    # Ensure we have at least the required fields
    formatted = {
        "name": row_data.get("name", ""),
        "synonyms": row_data.get("synonyms", [row_data.get("name", "")]),
        "class": row_data.get("class", row_data.get("concept_class", "")),
        "datatype": row_data.get("datatype", row_data.get("data_type", "")),
    }
    
    # Add optional fields if present
    optional_fields = ["units", "description", "usage_context", "frequency", "local_id"]
    for field in optional_fields:
        if field in row_data and row_data[field]:
            formatted[field] = row_data[field]
    
    return formatted


def format_candidate(candidate, rank):
    """Format a single candidate for the prompt."""
    formatted = {
        "concept_id": candidate.get("id", ""),
        "display_name": candidate.get("display_name", ""),
        "class": candidate.get("concept_class", ""),
        "datatype": candidate.get("datatype", ""),
        "owner": candidate.get("owner", ""),
        "repository": candidate.get("source", ""),
        "status": "Active" if candidate.get("retired", False) is False else "Inactive"
    }
    
    # Add search metadata
    if "search_meta" in candidate:
        search_meta = candidate["search_meta"]
        formatted["search_meta"] = [{
            "match_algorithm": "combined",
            "score": search_meta.get("search_score", 0),
            "match_type": "semantic",
            "matched_fields": []
        }]
    
    # Add optional fields
    optional_fields = ["definition", "synonyms", "version", "hierarchy_path"]
    for field in optional_fields:
        if field in candidate and candidate[field]:
            formatted[field] = candidate[field]
    
    return formatted


def format_llm_judge_prompt(input_row, candidates, project_context=None, debug=False):
    """
    Format the complete prompt for LLM evaluation.
    
    Args:
        input_row: Dictionary containing the input term data
        candidates: List of candidate matches
        project_context: Optional project-specific context (uses default if None)
        debug: If True, includes additional debugging information
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    if project_context is None:
        project_context = DEFAULT_PROJECT_CONTEXT
    
    # Format input row
    formatted_input = format_input_row(input_row)
    
    # Format candidates
    formatted_candidates = []
    for i, candidate in enumerate(candidates):
        formatted_candidates.append(format_candidate(candidate, i + 1))
    
    # Build user prompt
    user_prompt = f"""Evaluate the following medical terminology matching task:

## Project Context
{json.dumps(project_context, indent=2)}

## Input Row
{json.dumps(formatted_input, indent=2)}

## Candidate Pool
{json.dumps(formatted_candidates, indent=2)}

## Task
Please evaluate these candidates and provide your recommendation following the structured output template. Focus on:
1. Semantic alignment between the input term and candidates
2. Clinical safety and appropriateness
3. Implementation viability

Respond with a JSON object following this structure:
{json.dumps(OUTPUT_TEMPLATE, indent=2)}

Important: Your response must be a valid JSON object only, with no additional text or explanation outside the JSON."""

    if debug:
        debug_info = f"\n\n## Debug Information\n- Number of candidates: {len(candidates)}\n- Input row keys: {list(input_row.keys())}"
        user_prompt += debug_info
    
    return SYSTEM_PROMPT, user_prompt


def parse_llm_response(response_text):
    """
    Parse the LLM response to extract recommendation and rationale.
    
    Args:
        response_text: Raw text response from the LLM
        
    Returns:
        Tuple of (recommendation, rationale) or (None, None) if parsing fails
    """
    try:
        # Try to parse as JSON
        response_json = json.loads(response_text)
        
        # Extract recommendation
        recommendation = None
        if "primary_candidate" in response_json and response_json["primary_candidate"]:
            recommendation = response_json["primary_candidate"].get("concept_id")
        
        # Extract rationale
        rationale = ""
        if "rationale" in response_json:
            if isinstance(response_json["rationale"], dict):
                rationale = response_json["rationale"].get("narrative", "")
            else:
                rationale = str(response_json["rationale"])
        
        # If no narrative rationale, try to construct one from structured data
        if not rationale and "rationale" in response_json and "structured" in response_json["rationale"]:
            structured = response_json["rationale"]["structured"]
            rationale = f"Semantic: {structured.get('semantic_alignment', 'N/A')}. " \
                       f"Safety: {structured.get('clinical_safety', 'N/A')}. " \
                       f"Specificity: {structured.get('specificity_level', 'N/A')}."
        
        return recommendation, rationale
        
    except json.JSONDecodeError:
        # If not valid JSON, try to extract information from text
        # This is a fallback for cases where the LLM doesn't follow instructions perfectly
        return None, "Failed to parse LLM response"
    except Exception as e:
        return None, f"Error parsing response: {str(e)}"