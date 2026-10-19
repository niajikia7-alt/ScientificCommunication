#!/bin/bash
# Stop at the first step that fails
set -euo pipefail

existing_corpus=path_to_parquet_file.parquet
pdf_dir=path_to_download_pdfs/
xml_dir=path_to_extract_xmls/
dfs_dir=path_to_dump_dataframes/
log_dir=logs/
# Only look for papers from this year onwards (leave empty to check all years)
min_year=2025

mkdir -p $pdf_dir $xml_dir $dfs_dir $log_dir
year_arg=${min_year:+--min-year $min_year}

# Download ACL anthology and convert it into dataframe
# Outputs by default: anthology.bib.gz (raw download); anthology.parquet (parsed into Pandas dataframe)
python get_anthology.py

# Compare existing corpus version(s) against anthology to find missing papers
# Note: multiple corpus files can be passed
# Outputs by default: missing_papers.txt (entirely absent); empty_papers.txt (present but with null full_text)
python find_missing_papers.py $existing_corpus $year_arg

# Download PDFs of missing papers, optionally double-checking against already available PDF files
# Note: you can pass multiple input files (with paper IDs) and multiple directories with existing PDF files
# Papers that could not be downloaded are listed in failed_papers.txt
python get_missing_papers.py missing_papers.txt --pdf-dirs $pdf_dir --out-dir $pdf_dir 2> $log_dir/download.log

# Uncomment to also download empty papers (limited likelihood that they have become available)
# python get_missing_papers.py empty_papers.txt --pdf-dirs $pdf_dir --out-dir $pdf_dir 2>> $log_dir/download.log

# Convert PDFs into XML files
# Start Docker container for GROBID server in detached mode.
# GROBID needs a lot of memory (16 GB+ recommended); if it crashes, Docker
# restarts it and get_xml_from_pdf.py waits for it and retries.
docker rm -f grobid > /dev/null 2>&1 || true
docker run -d --name grobid --restart unless-stopped --init --ulimit core=0 -p 8070:8070 lfoppiano/grobid:0.8.1

# Run PDF to XML conversion (waits for GROBID to start)
# PDFs that could not be converted are listed in failed_xmls.txt
python get_xml_from_pdf.py $pdf_dir $xml_dir 2> $log_dir/grobid.log

# Stop GROBID container
docker rm -f grobid

# Convert XML into Pandas dataframe
python parse_grobid_extraction.py $xml_dir $dfs_dir/papers_content.parquet

# Add metadata and write out new corpus
python get_metadata.py $dfs_dir/papers_content.parquet $dfs_dir/corpus_update.parquet
