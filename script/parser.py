import os
import re
from collections import defaultdict


def parse_token_distribution(log_dir):
    """
    Parses log files in the specified directory to calculate the distribution
    of max token sizes.

    Args:
        log_dir (str): Path to the directory containing log files.

    Returns:
        dict: A dictionary where keys are token sizes and values are their counts.
    """
    token_distribution = defaultdict(int)
    log_pattern = re.compile(r"wiki_batch_(\d+)\.log")
    token_size_pattern = re.compile(r"Max Token Size in Batch: (\d+)")

    # Iterate through all files in the directory
    for file_name in os.listdir(log_dir):
        if log_pattern.match(file_name):  # Match log file pattern
            file_path = os.path.join(log_dir, file_name)
            print(f"Processing file: {file_path}")
            # ofile.write(f"Processing file: {file_path}\n")
            batch_num = int(log_pattern.match(file_name).group(1))

            output_file = os.path.join(log_dir, f"out_{batch_num}.txt")
            ofile = open(output_file, "w")
            with open(file_path, "r") as log_file:
                for line in log_file:
                    match = token_size_pattern.search(line)
                    if match:
                        token_size = int(match.group(1))
                        token_distribution[token_size] += 1

            for token_size, count in sorted(token_distribution.items()):
                print(f"Token Size: {token_size}, Count: {count}")
                ofile.write(f"{token_size}, {count}\n")
            token_distribution = defaultdict(int)  # Reset for the next batch
            ofile.close()
    # Print the distribution
    return token_distribution


def main():
    log_directory = (
        "/mnt/nvme1n1/shaobol2/results"  # Replace with the actual path to your log files
    )
    distribution = parse_token_distribution(log_directory)

    # Print the distribution
    # print("Token Size Distribution:")
    # for token_size, count in sorted(distribution.items()):
    #     print(f"Token Size: {token_size}, Count: {count}")

    # # Optionally, save the distribution to a file
    # output_file = "token_size_distribution.txt"
    # with open(output_file, "w") as f:
    #     for token_size, count in sorted(distribution.items()):
    #         f.write(f"Token Size: {token_size}, Count: {count}\n")
    # print(f"Distribution saved to {output_file}")


if __name__ == "__main__":
    main()
