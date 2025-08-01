'''
CLI script to use an OCL matching API to match a set of medical terms to a target repository. The script accepts a spreadsheet as input, and it outputs the same spreadsheet with additional columns containing the match results.

Usage examples:

1. Basic usage:
python match.py -t=[your-token-here] -i=./samples/sample01.csv -o=./output/results.csv -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ -e=https://api.dev.openconceptlab.org

2. With semantic search and verbosity:
python match.py -t=[your-token-here] -i=./samples/sample01.csv -o=./output/results.csv -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ -e=https://api.dev.openconceptlab.org --endpoint=/concepts/$match/ -s=true -v=2

3. With top-n calculation (adds a "top-n" column showing which candidate matched the correct map):
python match.py -t=[your-token-here] -i=./samples/sample01.csv -o=./output/results.csv -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ -e=https://api.dev.openconceptlab.org --correctmap=loinc_code -n=5

4. With LOINC type filtering (only return LOINC Part codes):
python match.py -t=[your-token-here] -i=./samples/sample01.csv -o=./output/results.csv -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ -e=https://api.dev.openconceptlab.org --filter-loinc-type=Part --filter-fetch-factor=3

5. With both top-n calculation and LOINC filtering:
python match.py -t=[your-token-here] -i=./samples/sample01.csv -o=./output/results.csv -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ -e=https://api.dev.openconceptlab.org --correctmap=loinc_code --filter-loinc-type=LOINC -n=10

CLI arguments:
-i, --inputfile: Input file
-e, --env: environment, e.g. https://api.dev.openconceptlab.org
-t, --token: OCL API token
-r, --repo: Target repository, e.g. /orgs/CIEL/sources/CIEL/v2024-10-04/
--endpoint: $match endpoint, e.g. /concepts/$match/
-s, --semantic: Semantic search
-v, --verbosity: Verbosity
-c, --chunk: Max chunk size to send to $match algorithm at a time
--numcandidates: Approximate number of nearest neighbor candidates to consider on each shard
--knearest: Number of nearest neighbors to consider for each row
-n, --topn: Number of top candidates to save for each row
-o, --outputfile: Output file
--columnmap_filename: JSON file containing mapping columns in the input file to fields that the $match endpoint expects
--correctmap: Column name containing the correct map for top-n calculation (adds a top-n column to output)
--filter-loinc-type: Filter candidates by LOINC code type (LOINC, Part, Group, List, Answers)
--filter-fetch-factor: Multiplier for fetching extra candidates when filtering (default: 2.0)
'''

import argparse
import time
import json
import requests
import pandas as pd
import sys


def matches_loinc_type(code, loinc_type):
    """
    Check if a LOINC code matches the specified type based on prefix.
    
    LOINC Code Types:
    - LOINC: Regular codes (no special prefix like LP, LG, LL, LA)
    - Part: LP prefix
    - Group: LG prefix
    - List: LL prefix
    - Answers: LA prefix
    """
    if not code or not loinc_type:
        return True
    
    code = str(code).strip()
    
    if loinc_type == "LOINC":
        # Regular LOINC codes don't start with the special prefixes
        return not any(code.startswith(prefix) for prefix in ["LP", "LG", "LL", "LA"])
    elif loinc_type == "Part":
        return code.startswith("LP")
    elif loinc_type == "Group":
        return code.startswith("LG")
    elif loinc_type == "List":
        return code.startswith("LL")
    elif loinc_type == "Answers":
        return code.startswith("LA")
    
    return True


def match(api_token="", api_match_url="", input_filename="", target_repo="",
          column_map={}, semantic=False, max_chunk_size=200,
          knn_num_candidates=1000, knearest=5, top_n=5, verbosity=0,
          correct_map_column="", filter_loinc_type="", filter_fetch_factor=2.0):
    start_time = time.time()

    # API request parameters
    # When filtering, fetch more candidates to ensure we get enough after filtering
    fetch_limit = int(top_n * filter_fetch_factor) if filter_loinc_type else top_n
    
    params = {
        "includeSearchMeta": True,
        "semantic": semantic,
        "limit": fetch_limit,
        "kNearest": knearest,
        "numCandidates": knn_num_candidates,
        "bestMatch": False
    }
    headers = {}
    if api_token:
        headers["Authorization"] = "Token %s" % (api_token)

    # Print script configuration
    if verbosity:
        print("\nCONFIGURATION:")
        print("  Matching API endpoint: ", api_match_url)
        if api_token:
            print("  API token: *******")
        print("  Input Filename: ", input_filename)
        print("  Target Repository: ", target_repo)
        print("  Semantic Search: ", semantic)
        print("  Top-N candidates to save: ", top_n)
        if filter_loinc_type:
            print("  LOINC Type Filter: ", filter_loinc_type)
            print("  Filter Fetch Factor: ", filter_fetch_factor)
            print("  Fetching up to: ", fetch_limit, "candidates per row")
        print("  Max Chunk Size: ", max_chunk_size)
        print("  kNN Number of Candidates: ", knn_num_candidates)
        print("  k-Nearest: ", knearest)
        print("  Verbosity: ", verbosity)
        if column_map:
            print("  Column Mapping: ", json.dumps(column_map, indent=4))

    # Load input file
    import_file_type = input_filename.split('.')[-1]  # e.g. csv, xlsx
    if import_file_type == 'csv':
        df = pd.read_csv(input_filename)
    elif import_file_type == 'xlsx':
        df = pd.read_excel(input_filename)
    else:
        print("Error: Unknown file type", import_file_type)
        sys.exit(1)

    # Store original columns to preserve them in output
    original_columns = df.columns.tolist()
    
    # Process import file: Change column names, convert to dictionary and chunk
    df.rename(columns=column_map, inplace=True)
    data = json.loads(df.to_json(orient="records"))  # serialize/deserialize to get rid of funky datatypes
    list_of_chunked_data = [data[i * max_chunk_size:(i + 1) * max_chunk_size] 
                            for i in range((len(data) + max_chunk_size - 1) // max_chunk_size)]
    
    if verbosity:
        print("\nINPUT FILE:")
        print("  Total Rows: ", len(df))
        print("  # Chunks: ", len(list_of_chunked_data))

    # Initialize results storage
    all_results = []
    chunk_num = 0
    cumulative_chunk_elapsed_time = 0
    
    print("\nMATCHING:")
    for chunk_index, chunk in enumerate(list_of_chunked_data):
        # Prepare chunk data
        new_chunk = []
        for row in chunk:
            row['name'] = row.get('name', None) or ""
            row['synonyms'] = [row['name']]
            row.pop('id', None)
            new_chunk.append(row)

        # Request match results
        chunk_num += 1
        payload = {
            "rows": new_chunk,
            "target_repo_url": target_repo
        }
        
        if verbosity:
            print(f"Chunk #: {chunk_num} ({len(new_chunk)} rows)")
            print(f"  {api_match_url} {json.dumps(params)}")
        
        chunk_start_time = time.time()
        try:
            r = requests.post(api_match_url, json=payload, params=params, headers=headers)
            r.raise_for_status()
            response = r.json()
        except requests.exceptions.RequestException as e:
            print(f"  Error in chunk {chunk_num}: {str(e)}")
            # Add empty results for this chunk
            for i in range(len(new_chunk)):
                all_results.append({})
            continue
        
        chunk_elapsed_time = time.time() - chunk_start_time
        cumulative_chunk_elapsed_time += chunk_elapsed_time
        chunk_average_time_per_row = chunk_elapsed_time / len(new_chunk)
        
        if verbosity:
            print(f"  Chunk Match Time: {round(chunk_elapsed_time, 4)} sec ({round(chunk_average_time_per_row, 4)} sec/row)")

        # Process results for each row in the chunk
        for row_index, row_matches in enumerate(response):
            # Get the original row index
            original_row_index = chunk_index * max_chunk_size + row_index
            
            # Sort candidates by search score
            if "results" in row_matches and row_matches["results"]:
                row_matches["results"] = sorted(
                    row_matches["results"], 
                    key=lambda candidate: candidate["search_meta"]["search_score"], 
                    reverse=True
                )
            
            # Extract top-N candidates
            result_dict = {}
            candidates = row_matches.get("results", [])
            
            # Apply LOINC type filter if specified
            if filter_loinc_type:
                filtered_candidates = [
                    candidate for candidate in candidates
                    if matches_loinc_type(candidate.get("id", ""), filter_loinc_type)
                ]
            else:
                filtered_candidates = candidates
            
            # Add filtered candidates to results (up to top_n)
            for i in range(min(top_n, len(filtered_candidates))):
                candidate = filtered_candidates[i]
                rank_prefix = f"{i+1:02d}"  # 01, 02, 03, etc.
                
                result_dict[f"{rank_prefix}_code"] = candidate.get("id", "")
                result_dict[f"{rank_prefix}_name"] = candidate.get("display_name", "")
                result_dict[f"{rank_prefix}_score"] = round(candidate["search_meta"].get("search_score", 0), 4)
            
            # Fill in empty columns for candidates not found
            for i in range(len(filtered_candidates), top_n):
                rank_prefix = f"{i+1:02d}"
                result_dict[f"{rank_prefix}_code"] = ""
                result_dict[f"{rank_prefix}_name"] = ""
                result_dict[f"{rank_prefix}_score"] = ""
            
            # Calculate top-n value if correct_map_column is provided
            if correct_map_column:
                result_dict["top-n"] = ""
                # Get the correct map value from the original data
                if original_row_index < len(data):
                    original_row = data[original_row_index]
                    correct_map = str(original_row.get(correct_map_column, "")).strip()
                    
                    # Skip empty values and "new" concepts
                    if correct_map and correct_map.lower() != "new":
                        # Check each filtered candidate for a match
                        for i, candidate in enumerate(filtered_candidates[:top_n]):
                            if str(candidate.get("id", "")).strip() == correct_map:
                                result_dict["top-n"] = i + 1
                                break
            
            all_results.append(result_dict)

    # Combine original data with results
    results_df = pd.DataFrame(all_results)
    
    # Reload original dataframe to preserve original column names
    if import_file_type == 'csv':
        output_df = pd.read_csv(input_filename)
    else:
        output_df = pd.read_excel(input_filename)
    
    # Concatenate with results
    output_df = pd.concat([output_df, results_df], axis=1)
    
    # Calculate final statistics
    elapsed_seconds = time.time() - start_time
    
    if verbosity:
        print(f"\nRESULTS:")
        print(f"  Total rows processed: {len(df)}")
        print(f"  Total Elapsed Time: {round(elapsed_seconds, 2)} sec")
        print(f"  Total Match Time: {round(cumulative_chunk_elapsed_time, 2)} sec")
        print(f"  Average Match Time per Row: {round(cumulative_chunk_elapsed_time / len(df), 2)} sec/row")

    return output_df


# CLI
parser = argparse.ArgumentParser(prog='match.py', description='Match terms to a target repository using OCL API')
parser.add_argument('-t', '--token', required=True, help="OCL API token")
parser.add_argument('-i', '--inputfile', required=True, help="File of input data to be mapped")
parser.add_argument('-r', '--repo', help="Map target repo, e.g. /orgs/CIEL/sources/CIEL/v2024-10-04/", 
                    default="/orgs/CIEL/sources/CIEL/v2024-10-04/")
parser.add_argument('-e', '--env', default="http://localhost:8000", 
                    help="OCL API environment, e.g. https://api.qa.openconceptlab.org")
parser.add_argument('--endpoint', default="/concepts/$match/", help="$match endpoint, e.g. /concepts/$match/")
parser.add_argument('--columnmap_filename', help="JSON file containing column mappings")
parser.add_argument('-s', '--semantic', default='false', choices=['true', 'false'])
parser.add_argument('-c', '--chunk', type=int, default=200, 
                    help="Max chunk size to send to $match algorithm at a time")
parser.add_argument('--numcandidates', type=int, default=5000, 
                    help="Approximate number of nearest neighbor candidates to consider on each shard")
parser.add_argument('--knearest', type=int, default=5, 
                    help="Number of nearest neighbors to consider for each row")
parser.add_argument('-n', '--topn', type=int, default=5, help="Number of top candidates to save for each row")
parser.add_argument('-v', '--verbosity', type=int, default=0)
parser.add_argument('-o', '--outputfile', required=True, help="Output file to save the results")
parser.add_argument('--correctmap', help="Column name containing the correct map for top-n calculation")
parser.add_argument('--filter-loinc-type', choices=['LOINC', 'Part', 'Group', 'List', 'Answers'],
                    help="Filter candidates by LOINC code type")
parser.add_argument('--filter-fetch-factor', type=float, default=2.0,
                    help="Multiplier for fetching extra candidates when filtering (default: 2.0)")

args = parser.parse_args()

# Convert columnmap_filename argument to dictionary, if provided
column_map = {}
if args.columnmap_filename:
    try:
        with open(args.columnmap_filename, 'r') as f:
            column_map = json.load(f)
    except Exception as e:
        print(f"Error loading column map file: {str(e)}")
        sys.exit(1)

# Run match
api_match_url = args.env + args.endpoint
semantic = args.semantic == 'true'

try:
    output_df = match(
        api_token=args.token,
        api_match_url=api_match_url,
        input_filename=args.inputfile,
        target_repo=args.repo,
        column_map=column_map,
        semantic=semantic,
        max_chunk_size=args.chunk,
        knn_num_candidates=args.numcandidates,
        knearest=args.knearest,
        top_n=args.topn,
        verbosity=args.verbosity,
        correct_map_column=args.correctmap or "",
        filter_loinc_type=getattr(args, 'filter_loinc_type', '') or "",
        filter_fetch_factor=args.filter_fetch_factor
    )
    
    # Save output file
    output_file_type = args.outputfile.split('.')[-1]
    if output_file_type == 'csv':
        output_df.to_csv(args.outputfile, index=False)
    elif output_file_type == 'xlsx':
        output_df.to_excel(args.outputfile, index=False)
    else:
        print(f"Error: Unknown output file type '{output_file_type}'. Using CSV format.")
        output_df.to_csv(args.outputfile, index=False)
    
    print(f"\nOutput saved to: {args.outputfile}")
    
except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)