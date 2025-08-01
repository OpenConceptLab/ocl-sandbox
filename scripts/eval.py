'''
CLI script to evaluate the results of one or more match.py runs and to produce a table of top-n metrics.
The top-n metric is defined as: Proportion of rows for which the correct map was in the top-n candidates
returned by the matching algorithm. Scores are expected to be in columns named 01_score, 02_score, etc.
The correct map is expected to be in a column named by the --correctmap argument.

Example output (without groupby):
filename,rowcount,top-1,top-2,top-3,top-4,top-5
inputfile1.csv,400,0.0500,0.0800,0.1200,0.1500,0.2000
inputfile2.csv,350,0.0600,0.0900,0.1300,0.1600,0.2100

Example output (with groupby):
filename,group,rowcount,top-1,top-2,top-3,top-4,top-5
inputfile1.csv,*,400,0.0500,0.0800,0.1200,0.1500,0.2000
inputfile1.csv,Test,150,0.0700,0.1000,0.1400,0.1700,0.2200
inputfile1.csv,Finding,250,0.0300,0.0600,0.1000,0.1300,0.1800

Usage:
python eval.py -c=correct_map_concept_id -v=2 <inputfile1> <inputfile2> ...
python eval.py -c=loinc_code -g=cl -v=2 <inputfile1> <inputfile2> ...

CLI arguments:
-v, --verbosity: Verbosity
-c, --correctmap: Column name containing the correct map (e.g. correct_map_concept_id)
-n, --topn: Number of top-n metrics to calculate (e.g. 5)
-g, --groupby: Column name to group results by (e.g. cl for class)
'''

import argparse
import pandas as pd
import os
import sys


def evaluate_subset(df, correct_map_column, top_n=5, verbosity=0, subset_name=""):
    """
    Evaluate a subset of data and calculate top-n metrics.
    
    Returns a dictionary with the evaluation metrics.
    """
    # Initialize counters
    num_correct_matches_in_top_n = [0] * top_n
    num_excluded = 0
    num_new_concept = 0
    num_valid_rows = 0
    
    # Check for required result columns
    code_columns = [f"{i:02d}_code" for i in range(1, top_n + 1)]
    missing_columns = [col for col in code_columns if col not in df.columns]
    if missing_columns:
        return None
    
    # Evaluate each row
    for index, row in df.iterrows():
        correct_map = str(row[correct_map_column]).strip() if pd.notna(row[correct_map_column]) else ""
        
        # Skip rows with no correct map, empty values, or "new" concepts
        if not correct_map:
            num_excluded += 1
            continue
        elif correct_map.lower() == "new":
            num_new_concept += 1
            continue
        
        num_valid_rows += 1
        
        # Check if the correct map appears in the top-n results
        for i in range(top_n):
            candidate_code = str(row[f"{i+1:02d}_code"]).strip() if pd.notna(row[f"{i+1:02d}_code"]) else ""
            
            if correct_map == candidate_code:
                # Found a match at position i+1
                # Count it for all top-n metrics from this position onwards
                for j in range(i, top_n):
                    num_correct_matches_in_top_n[j] += 1
                
                if verbosity >= 3 and subset_name:
                    print(f"  [{subset_name}] Row {index}: Match found at position {i+1}")
                break
        else:
            # No match found in top-n
            if verbosity >= 3 and subset_name:
                print(f"  [{subset_name}] Row {index}: No match found in top-{top_n}")
    
    # Calculate proportions
    if num_valid_rows == 0:
        return None
    
    proportions = [count / num_valid_rows for count in num_correct_matches_in_top_n]
    
    return {
        'total_rows': len(df),
        'valid_rows': num_valid_rows,
        'excluded_rows': num_excluded,
        'new_concepts': num_new_concept,
        'proportions': proportions
    }


def evaluate_file(filename, correct_map_column, top_n=5, verbosity=0, groupby_column=None):
    """
    Evaluate a single match.py output file and calculate top-n metrics.
    
    Returns a dictionary with the evaluation results, including group-specific results if groupby is specified.
    """
    if verbosity >= 1:
        print(f"\nProcessing: {filename}")
    
    # Load the file
    file_type = filename.split('.')[-1].lower()
    try:
        if file_type == 'csv':
            df = pd.read_csv(filename)
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(filename)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        return None
    
    # Validate that the correct map column exists
    if correct_map_column not in df.columns:
        print(f"Error: Column '{correct_map_column}' not found in {filename}")
        print(f"Available columns: {', '.join(df.columns.tolist())}")
        return None
    
    # Validate groupby column if specified
    if groupby_column and groupby_column not in df.columns:
        print(f"Warning: Groupby column '{groupby_column}' not found in {filename}")
        groupby_column = None
    
    # Calculate overall metrics
    overall_metrics = evaluate_subset(df, correct_map_column, top_n, verbosity, "Overall")
    if overall_metrics is None:
        print(f"Warning: No valid rows to evaluate in {filename}")
        return None
    
    # Prepare results
    results = {
        'filename': os.path.basename(filename),
        'overall': overall_metrics,
        'groups': {}
    }
    
    # Calculate group-specific metrics if requested
    if groupby_column:
        unique_groups = df[groupby_column].dropna().unique()
        if verbosity >= 2:
            print(f"  Found {len(unique_groups)} unique groups in column '{groupby_column}'")
        
        for group_value in sorted(unique_groups):
            group_df = df[df[groupby_column] == group_value]
            group_metrics = evaluate_subset(group_df, correct_map_column, top_n, verbosity, f"Group={group_value}")
            if group_metrics:
                results['groups'][str(group_value)] = group_metrics
                if verbosity >= 2:
                    print(f"  Group '{group_value}': {group_metrics['valid_rows']} valid rows, ", end="")
                    for i, prop in enumerate(group_metrics['proportions'], 1):
                        print(f"top-{i}={prop:.4f}", end=" ")
                    print()
    
    if verbosity >= 2:
        overall = results['overall']
        print(f"  Overall - Total rows: {overall['total_rows']}")
        print(f"  Overall - Valid rows: {overall['valid_rows']}")
        print(f"  Overall - Excluded rows: {overall['excluded_rows']}")
        print(f"  Overall - New concepts: {overall['new_concepts']}")
        print(f"  Overall - Top-n metrics: ", end="")
        for i, prop in enumerate(overall['proportions'], 1):
            print(f"top-{i}={prop:.4f}", end=" ")
        print()
    
    return results


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        prog='eval.py',
        description='Evaluate the results of one or more match.py runs and produce top-n metrics'
    )
    parser.add_argument(
        'inputfiles',
        nargs='+',
        help='One or more match.py output files to evaluate'
    )
    parser.add_argument(
        '-c', '--correctmap',
        required=True,
        help='Column name containing the correct map (e.g. correct_map_concept_id)'
    )
    parser.add_argument(
        '-n', '--topn',
        type=int,
        default=5,
        help='Number of top-n metrics to calculate (default: 5)'
    )
    parser.add_argument(
        '-v', '--verbosity',
        type=int,
        default=0,
        help='Verbosity level (0-3, default: 0)'
    )
    parser.add_argument(
        '-g', '--groupby',
        help='Column name to group results by (e.g. cl for class)'
    )
    
    args = parser.parse_args()
    
    # Process each input file
    all_results = []
    for filename in args.inputfiles:
        if not os.path.exists(filename):
            print(f"Error: File not found: {filename}")
            continue
        
        results = evaluate_file(
            filename=filename,
            correct_map_column=args.correctmap,
            top_n=args.topn,
            verbosity=args.verbosity,
            groupby_column=args.groupby
        )
        
        if results:
            all_results.append(results)
    
    # Generate summary table
    if not all_results:
        print("Error: No files were successfully evaluated")
        sys.exit(1)
    
    # Print header
    print("\nSummary Results:")
    if args.groupby:
        headers = ["filename", "group", "rowcount"] + [f"top-{i}" for i in range(1, args.topn + 1)]
    else:
        headers = ["filename", "rowcount"] + [f"top-{i}" for i in range(1, args.topn + 1)]
    print(",".join(headers))
    
    # Print results for each file
    for result in all_results:
        if args.groupby:
            # Print overall results with group = "*"
            row = [result['filename'], "*", str(result['overall']['valid_rows'])]
            row.extend([f"{prop:.4f}" for prop in result['overall']['proportions']])
            print(",".join(row))
            
            # Print group-specific results
            for group_name in sorted(result['groups'].keys()):
                group_data = result['groups'][group_name]
                row = [result['filename'], group_name, str(group_data['valid_rows'])]
                row.extend([f"{prop:.4f}" for prop in group_data['proportions']])
                print(",".join(row))
        else:
            # Original format without grouping
            row = [result['filename'], str(result['overall']['valid_rows'])]
            row.extend([f"{prop:.4f}" for prop in result['overall']['proportions']])
            print(",".join(row))


if __name__ == "__main__":
    main()
