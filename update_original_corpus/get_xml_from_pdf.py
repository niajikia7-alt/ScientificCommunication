import argparse
import logging
import os
import time

import requests


def wait_for_grobid(url: str, timeout: int) -> bool:
    """Waits until the GROBID server answers, for up to `timeout` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f'{url}/api/isalive', timeout=5).text.strip() == 'true':
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    return False


def process_pdf(pdf_file: str, xml_file: str, url: str,
                retries: int, wait: int) -> bool:
    """Converts PDF into XML file. Returns True on success.

    If GROBID is down (e.g. it crashed for lack of memory and is being
    restarted by Docker), waits for it to come back and tries again.
    Failed conversions are never written to disk.
    """
    for attempt in range(1, retries + 1):
        try:
            with open(pdf_file, 'rb') as f:
                rsp = requests.post(f'{url}/api/processFulltextDocument',
                                    files={'input': f}, timeout=300)
            if rsp.status_code == 200 and rsp.content:
                with open(xml_file, 'wb') as f:
                    f.write(rsp.content)
                return True
            error = f'HTTP {rsp.status_code}'
            if rsp.status_code != 503:
                # GROBID could not process this PDF; retrying won't help
                # (503 = server busy, which is worth retrying)
                logging.warning(f'{pdf_file}\t{error}')
                return False
        except requests.RequestException as e:
            error = e
        logging.warning(f'{pdf_file}\tAttempt {attempt} failed ({error}), '
                        f'waiting for GROBID')
        if not wait_for_grobid(url, wait):
            logging.error(f'GROBID did not come back within {wait}s')
    logging.warning(f'{pdf_file}\tFailed after {retries} attempts')
    return False


def main():
    desc = 'Converts paper PDFs into XML files using a running GROBID server.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('in_dir', help='input directory with paper PDFs')
    parser.add_argument('out_dir', help='output directory to write XMLs')
    parser.add_argument('--grobid-url', default='http://localhost:8070',
                        help='address of the GROBID server')
    parser.add_argument('--retries', type=int, default=3,
                        help='attempts per PDF')
    parser.add_argument('--wait', type=int, default=180,
                        help='seconds to wait for GROBID to (re)start')
    parser.add_argument('--failed-file', default='failed_xmls.txt',
                        help='output file listing PDFs that failed')
    args = parser.parse_args()
    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(message)s',
                        level=logging.INFO)

    os.makedirs(args.out_dir, exist_ok=True)
    pdf_files = sorted(f for f in os.listdir(args.in_dir) if f.endswith('.pdf'))

    logging.info(f'Processing {len(pdf_files)} PDF files.')
    logging.info(f'Input directory:  {args.in_dir}')
    logging.info(f'Output directory: {args.out_dir}')

    if not wait_for_grobid(args.grobid_url, args.wait):
        raise SystemExit(f'GROBID is not running at {args.grobid_url}')

    done, skipped, failed = 0, 0, []
    for i, pdf_file in enumerate(pdf_files):
        xml_file = os.path.join(args.out_dir, f'{pdf_file[:-4]}.tei.xml')
        if os.path.isfile(xml_file) and os.path.getsize(xml_file) > 0:
            skipped += 1
            continue
        if process_pdf(os.path.join(args.in_dir, pdf_file), xml_file,
                       args.grobid_url, args.retries, args.wait):
            done += 1
        else:
            failed.append(pdf_file)
        if (i + 1) % 100 == 0:
            logging.info(f'Processed {i + 1} files.')

    with open(args.failed_file, 'w') as f:
        f.writelines([p + '\n' for p in failed])
    logging.info(f'PDF to XML conversion done. Converted {done}, skipped '
                 f'{skipped} existing, {len(failed)} failed (listed in '
                 f'{args.failed_file}).')


if __name__ == '__main__':
    main()
