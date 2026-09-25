import argparse
import logging
import os
import random
import shutil
import urllib.request
from time import sleep
from urllib.error import HTTPError, URLError


def load_existing_pdfs(pdf_dirs: list[str] | None) -> set[str]:
    """Loads list of paper IDs already available as PDF files."""
    pdfs = set()
    if pdf_dirs is not None:
        for pdf_dir in pdf_dirs:
            pdfs.update(os.listdir(pdf_dir))
        pdfs = {f[:-4] for f in pdfs if f.endswith('.pdf')}

    return pdfs


def load_missing_papers(in_files: list[str]) -> set[str]:
    """Loads list of missing paper IDs from one-paper-per-line files."""
    papers = set()
    for in_file in in_files:
        with open(in_file, 'r') as f:
            papers.update(f.readlines())
    papers = {p.rstrip() for p in papers}
    return papers


def download_paper(acl_id: str, out_dir: str, base_url: str,
                   retries: int = 3, timeout: int = 60) -> bool:
    """Downloads paper PDF from anthology into `out_dir`.

    The PDF is first written to a temporary file and only renamed once the
    download is complete and looks like a PDF, so that interrupted downloads
    never leave broken files behind (which would be skipped on a rerun).
    Transient errors (timeouts, dropped connections, server errors) are
    retried with exponential backoff; 4xx errors (e.g. 404) are not.
    Returns True if the PDF was downloaded.
    """
    url = f'{base_url}/{acl_id}.pdf'
    out_file = os.path.join(out_dir, f'{acl_id}.pdf')
    tmp_file = out_file + '.part'

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as rsp, \
                 open(tmp_file, 'wb') as f:
                shutil.copyfileobj(rsp, f)
            with open(tmp_file, 'rb') as f:
                if f.read(5) != b'%PDF-':
                    raise ValueError('response is not a PDF')
            os.replace(tmp_file, out_file)
            logging.info(f'{acl_id}\tDone')
            return True
        except HTTPError as e:
            if e.code < 500:
                logging.warning(f'{acl_id}\t{e}')
                break
            error = e
        except (URLError, OSError, ValueError) as e:
            error = e
        if attempt < retries:
            logging.info(f'{acl_id}\tAttempt {attempt} failed ({error}), '
                         'retrying')
            sleep(2 ** attempt)
        else:
            logging.warning(f'{acl_id}\tFailed after {retries} attempts: '
                            f'{error}')

    if os.path.exists(tmp_file):
        os.remove(tmp_file)
    return False


def main():
    desc = 'Downloads paper PDFs from ACL anthology based on a list of '\
           'ACL paper IDs, skipping papers whose PDFs already exist locally.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('in_files', type=str, nargs='+',
                        help='files containing one-per-line ACL paper IDs')
    parser.add_argument('--pdf-dirs', type=str, nargs='+',
                        help='directories containing already downloaded PDFs')
    parser.add_argument('--out-dir', type=str, default='.',
                        help='directory where to download new PDFs')
    parser.add_argument('--retries', type=int, default=3,
                        help='download attempts per paper')
    parser.add_argument('--failed-file', type=str, default='failed_papers.txt',
                        help='output file listing papers that could not be '
                             'downloaded (can be passed back in to retry)')
    parser.add_argument('--base-url', type=str,
                        default='https://aclanthology.org',
                        help=argparse.SUPPRESS)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(message)s',
                        level=logging.INFO)

    missing_papers = load_missing_papers(args.in_files)
    existing_pdfs = load_existing_pdfs(args.pdf_dirs)
    to_download = missing_papers - existing_pdfs
    logging.info(f'Loading paper IDs from files: {args.in_files}')
    logging.info(f'Checking against PDFs in directories: {args.pdf_dirs}')
    logging.info(f'Downloading {len(to_download)} PDFs to: {args.out_dir}')

    failed = []
    for acl_id in sorted(to_download):
        if not download_paper(acl_id, args.out_dir, args.base_url,
                              retries=args.retries):
            failed.append(acl_id)
        sleep(random.randint(0, 3))

    with open(args.failed_file, 'w') as f:
        f.writelines([paper+'\n' for paper in failed])
    logging.info(f'Done. Downloaded {len(to_download) - len(failed)} PDFs, '
                 f'{len(failed)} failed (listed in {args.failed_file}).')

if __name__ == '__main__':
    main()