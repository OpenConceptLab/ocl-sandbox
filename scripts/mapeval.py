'''
Script to evaluate the performance of a matching algorithm. Can run a single set of
CLI arguments or a batch of CLI arguments by using the --csv argument. The script
outputs the results and summary to console or files, as specified.
Current metrics: top-n, elapsed time
Planned: auto-match is correct

Usage:
1. Run mapeval with a single set of CLI arguments -- output everything to the console:
python3 mapeval.py --key=mapeval01 -t=[your-token-here] -i=./samples/sample01.csv
    -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ --correctmap=correct_map_concept_id
    -s=false -v=2

2. Run mapeval with a single set of CLI arguments -- output results and summary to files
python3 mapeval.py --key=mapeval01 -t=[your-token-here] -i=./samples/sample01.csv
    -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ --correctmap=correct_map_concept_id
    -s=false -v=1 --outputfile=./output/sample01_output.json
    --summaryfile=./output/sample01_output_summary.csv

3. Run mapeval with semantic search enabled:
python3 mapeval.py --key=mapeval01 -t=[your-token-here] -i=./samples/sample01.csv
    -r=/orgs/CIEL/sources/CIEL/v2024-10-04/ --correctmap=correct_map_concept_id
    --columnmap_filename=./samples/columnmap.json -s=true -v=1 --numcandidates=1000
    --outputfile=./output/sample01_output.json --summaryfile=./output/sample01_output_summary.csv

4. Batch run mapeval with a CSV file containing multiple sets of CLI arguments:
python3 mapeval.py --csv=./samples/batch01.csv -t=[your-token-here]
    -e=https://api.dev.openconceptlab.org --endpoint=/concepts/\$match/ -v=1
    --outputfile=./output/batch01_output.json --summaryfile=./output/batch01_output_summary.csv

Further documentation:
https://docs.openconceptlab.org/en/latest/oclapi/apireference/match.html
'''
import argparse
import time
from datetime import datetime
import json
import requests
import pandas as pd

def mapeval(key="", api_token="", api_match_url="", input_filename="", target_repo="",
            correct_map_column_name="", column_map={}, semantic=False, max_chunk_size=200,
            knn_num_candidates=1000, top_n_threshold=5, knearest=5, verbosity=0):
    start_time = time.time()

    # CONSTANTS
    list_algorithm_keys = ["id", "name", "synonyms", "description", "concept_class", "datatype",
                           "same_as_map_codes", "other_map_codes"]
    params = {
        "includeSearchMeta": True,
        "semantic": semantic,
        "limit": top_n_threshold,
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
        print("  Key: ", key)
        print("  Matching API endpoint: ", api_match_url)
        if api_token:
            print("  API token: *******")
        print("  Input Filename: ", input_filename)
        print("  Target Repository: ", target_repo)
        print("  Correct Map Concept ID Column Name: ", correct_map_column_name)
        print("  Semantic Search: ", semantic)
        print("  Top-n Threshold: ", top_n_threshold)
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
        print("unknown file type", import_file_type)
        exit()

    # Process import file: Change column names, convert to dictionary and chunk
    df.rename(columns=column_map, inplace=True)
    data = json.loads(df.to_json(orient="records"))  # serialize/deserialize to get rid of funky datatypes
    list_of_chunked_data = [data[i * max_chunk_size:(i + 1) * max_chunk_size] for i in range((len(data) + max_chunk_size - 1) // max_chunk_size)]
    if verbosity:
        print("\nINPUT FILE:")
        print("  Total Rows: ", len(df))
        print("  # Chunks: ", len(list_of_chunked_data))

    # Match and evaluate one chunk at a time
    num_correct_matches_in_top_n = [0] * top_n_threshold
    num_auto_match = 0 # 'search_meta.match_type=very_high'
    num_excluded = 0
    num_new_concept_proposed = 0
    chunk_num = 0
    unmatched = []
    row_num = 0
    row_results = []
    cumulative_chunk_elapsed_time = 0
    print("\nMATCHING:")
    for chunk in list_of_chunked_data:
        chunk_match_count = 0
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
        r = requests.post(api_match_url, json=payload, params=params, headers=headers)
        chunk_elapsed_time = time.time() - chunk_start_time
        cumulative_chunk_elapsed_time += chunk_elapsed_time
        chunk_average_time_per_row = chunk_elapsed_time / len(new_chunk)
        response = r.json()
        if verbosity:
            print ("  Chunk Match Time: ", round(chunk_elapsed_time, 2), " (", round(chunk_average_time_per_row, 2), "sec/row )")

        # Evaluate the results one row_matches at a time
        for row_matches in response:
            row_num += 1

            # Sort row_matches["results"] by search_meta["search_score"]
            row_matches["results"] = sorted(row_matches["results"], key=lambda candidate: candidate["search_meta"]["search_score"], reverse=True)

            # Evaluate top-n metric
            if correct_map_column_name:
                if not row_matches["row"][correct_map_column_name]:
                    num_excluded += 1
                elif str(row_matches["row"][correct_map_column_name]).lower() == "new":
                    num_new_concept_proposed += 1
                else:
                    matched_candidate_index = next((index for index, candidate in enumerate(row_matches["results"]) if str(row_matches["row"][correct_map_column_name]) == str(candidate["id"])), None)
                    if matched_candidate_index is not None:
                        matched_candidate = row_matches["results"][matched_candidate_index]
                        if verbosity >= 2:
                            print(str(matched_candidate["id"]), " ", sep="", end="")
                        if matched_candidate['search_meta']['match_type'] == 'very_high':
                            num_auto_match += 1
                        for i in range(matched_candidate_index, top_n_threshold):
                            num_correct_matches_in_top_n[i] += 1
                        chunk_match_count += 1
                    else:
                        unmatched.append(row_matches['row'])

            # Sort candidate by search_meta["search_score"] - remove after this is applied in the API
            candidate_scores = [candidate["search_meta"]["search_score"] for candidate in row_matches["results"]]

            # Store candidate scores for analytics
            row_results.append(candidate_scores.copy())

        print("  Chunk Match Count: ", f"{chunk_match_count} out of {len(new_chunk)}  ({round((chunk_match_count/len(new_chunk)) * 100, 2)}%)")

    # Results
    elapsed_seconds = time.time() - start_time
    chunk_average_time_per_row = cumulative_chunk_elapsed_time / len(df)
    results = {
        "key": key,
        "timestamp": datetime.now().isoformat(),
        "total_rows": len(df),
        "num_auto_matches": num_auto_match,
        "num_correct_matches_in_top_n": num_correct_matches_in_top_n,
        "num_excluded_rows": num_excluded,
        "num_new_concept_proposed": num_new_concept_proposed,
        "total_elapsed_seconds": elapsed_seconds,
        "total_match_seconds": cumulative_chunk_elapsed_time,
        "total_processing_seconds": elapsed_seconds - cumulative_chunk_elapsed_time,
        "average_match_seconds_per_row": chunk_average_time_per_row,
        "row_candidate_scores": row_results
    }

    # Report results
    if verbosity:
        print("\nRESULTS:")
        print("  total_rows:", len(df))
        print("  num_auto_matches: ", num_auto_match)
        print("  num_correct_matches_in_top_n: ", end="")
        for i, value in enumerate(num_correct_matches_in_top_n, start=1):
            print(f"{i}:{value}", end=" ")
        print("\n  num_excluded_rows: ", num_excluded)
        print("  num_new_concept_proposed: ", num_new_concept_proposed)
        print("  num_to_match: ", len(df) - num_new_concept_proposed - num_excluded)
        print(f"  Total Elapsed Seconds: {round(elapsed_seconds, 2)} sec")
        print(f"  Total Match Seconds: {round(cumulative_chunk_elapsed_time,2)} sec")
        print(f"  Total Processing Seconds: {round(results['total_processing_seconds'],2)} sec")
        print(f"  Average Match Seconds per Row: {round(chunk_average_time_per_row, 2)} sec/row")

    # Print unmatched rows
    if verbosity >= 3:
        print("\n\nUNMATCHED:", len(unmatched))
        print(json.dumps(unmatched, indent=4))

    return results


# CLI
parser = argparse.ArgumentParser(prog='mapeval.py', description='Evaluate the performance of a matching algorithm')
parser.add_argument('-k', '--key', help="Key to identify the run")
parser.add_argument('-t', '--token', required=True, help="OCL API token")
parser.add_argument('-i', '--inputfile', help="File of input data to be mapped")
parser.add_argument('-r', '--repo', help="Map target repo, e.g. /orgs/CIEL/sources/CIEL/v2024-10-04/", default="/orgs/CIEL/sources/CIEL/v2024-10-04/")
parser.add_argument('-e', '--env', default="http://localhost:8000", help="OCL API environment, e.g. https://api.qa.openconceptlab.org")
parser.add_argument('--endpoint', default="/concepts/$match/", help="$match endpoint, e.g. /concepts/$match/")
parser.add_argument('--correctmap', default="correct_map_concept_id", help="Column name of the correct map")
parser.add_argument('--columnmap_filename', help="JSON file containing column mappings")
parser.add_argument('-s', '--semantic', default='false', choices=['true', 'false'])
parser.add_argument('-c', '--chunk', type=int, default=200, help="Max chunk size to send to $match algorithm at a time")
parser.add_argument('--numcandidates', type=int, default=5000, help="Approximate number of nearest neighbor candidates to consider on each shard")
parser.add_argument('--knearest', type=int, default=5, help="Number of nearest neighbors to consider for each row")
parser.add_argument('-n', '--topn', type=int, default=5, help="Number of results to consider for top-n test")
parser.add_argument('-v', '--verbosity', type=int, default=0)
parser.add_argument('-o', '--outputfile', help="Analytics output file to write the results")
parser.add_argument('--csv', help="CSV file with rows of mapeval parameters")
parser.add_argument('--summaryfile', help="Summary output CSV file")
args = parser.parse_args()


# Function to run mapeval with given arguments
def run_mapeval_with_args(args):
    # Convert columnmap_filename argument to dictionary, if provided
    column_map = {}
    if args.columnmap_filename:
        with open(args.columnmap_filename, 'r') as f:
            column_map = json.load(f)

    # Run mapeval
    api_match_url = args.env + args.endpoint
    run_results = mapeval(
        key=args.key,
        api_token=args.token,
        api_match_url=api_match_url,
        input_filename=args.inputfile,
        target_repo=args.repo,
        correct_map_column_name=args.correctmap,
        column_map=column_map,
        semantic=args.semantic,
        max_chunk_size=int(args.chunk),
        knn_num_candidates=int(args.numcandidates),
        top_n_threshold=int(args.topn),
        knearest=int(args.knearest),  # Pass knearest to mapeval
        verbosity=int(args.verbosity)
    )

    run_results["args"] = vars(args)
    return run_results


# Run mapeval for each CSV row or just a single set of CLI arguments
mapeval_results = []
if args.csv:
    verbosity = int(args.verbosity)
    csv_df = pd.read_csv(args.csv)
    csv_row_number = 0
    if verbosity:
        print(f"\nCSV mode: {args.csv}")
    for index, row in csv_df.iterrows():
        csv_row_number += 1

        # Skip row if 'skip' is set to True in the CSV
        if row.get('skip', False):
            if verbosity:
                print(f"\ncsv-row[{csv_row_number}]:{row.get('key', '')}  SKIPPED")
            continue

        # Set arguments for the current row
        row_args = argparse.Namespace(
            key=row.get('key', f"mapeval_{csv_row_number}"),
            token=row.get('token', args.token),
            inputfile=row.get('inputfile', args.inputfile),
            repo=row.get('repo', args.repo),
            env=row.get('env', args.env),
            endpoint=row.get('endpoint', args.endpoint),
            correctmap=row.get('correctmap', args.correctmap),
            columnmap_filename=row.get('columnmap_filename', args.columnmap_filename),
            semantic=row.get('semantic', args.semantic),
            chunk=row.get('chunk', args.chunk),
            numcandidates=row.get('numcandidates', args.numcandidates),
            topn=row.get('topn', args.topn),
            knearest=row.get('knearest', args.knearest),
            verbosity=verbosity
        )

        # Run mapeval with the current row arguments
        if verbosity:
            print(f"\ncsv-row[{csv_row_number}]:{row.get('key', '')}")
        mapeval_results.append(run_mapeval_with_args(row_args))
else:
    if not hasattr(args, 'key') or not args.key:
        args.key = "mapeval"
    mapeval_results.append(run_mapeval_with_args(args))

# Generate summary results of the entire run e.g. {"summary": [...], "results": [...]}
overall_summary = []
for result in mapeval_results:
    result_summary = {}
    result_summary["key"] = result.get("key", "")
    result_summary["total_rows"] = result.get("total_rows", 0)
    for i, value in enumerate(result["num_correct_matches_in_top_n"]):
        result_summary[f"top_{i+1}"] = value
    result_summary["num_auto_matches"] = result.get("num_auto_matches", 0)
    result_summary["total_elapsed_seconds"] = result.get("total_elapsed_seconds", 0)
    result_summary["average_match_seconds_per_row"] = result.get("average_match_seconds_per_row", 0)
    for key in result.keys():
        if key in ["key", "total_rows", "num_auto_matches", "total_elapsed_seconds",
                   "average_match_seconds_per_row", "args", "row_candidate_scores",
                   "num_correct_matches_in_top_n", "timestamp"]:
            continue
        elif isinstance(result[key], list) or isinstance(result[key], dict):
            continue
        result_summary[key] = result[key]
    for key in result["args"].keys():
        if key in ["key", "token"]:
            continue
        result_summary[f"args_{key}"] = result["args"][key]
    result_summary["timestamp"] = result.get("timestamp", "")
    overall_summary.append(result_summary)
if args.verbosity >= 2:
    print("\nOVERALL SUMMARY:")
    print(json.dumps(overall_summary, indent=4))

# Write summary output file as CSV (if specified)
if args.summaryfile:
    summary_df = pd.DataFrame(overall_summary)
    summary_df.to_csv(args.summaryfile, index=False)

# Write analytics output file (of the entire run)
final_output = {"summary": overall_summary, "results": mapeval_results}
if args.outputfile:
    with open(args.outputfile, 'w') as f:
        f.write(json.dumps(final_output, indent=4))

# Print results of the entire run
if args.verbosity >= 2:
    print("\nFINAL RESULTS:")
    print(json.dumps(mapeval_results, indent=4))
