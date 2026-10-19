import argparse
import logging
import os
import requests


def process_pdf(pdf_file: str, out_dir: str, grobid_url: str) -> None:
    """Converts PDF into XML file via the GROBID REST API."""
    xml_file = f'{os.path.basename(pdf_file)[:-4]}.tei.xml'
    xml_file = os.path.join(out_dir, xml_file)

    if os.path.isfile(xml_file):
        logging.warning(f'Skipping existing file: {xml_file}')
    else:
        with open(pdf_file, 'rb') as f:
            rsp = requests.post(f'{grobid_url}/api/processFulltextDocument',
                                files={'input': f}, timeout=300)
        # Don't write error responses, so that a rerun retries these PDFs
        if rsp.status_code != 200:
            logging.warning(f'{pdf_file}\tGROBID returned {rsp.status_code}')
            return
        with open(xml_file, 'wb') as f:
            f.write(rsp.content)


def main():
    desc = 'Converts paper PDFs into XML files using GROBID.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('in_dir', help='input directory with paper PDFs')
    parser.add_argument('out_dir', help='output directory to write XMLs')
    parser.add_argument('--grobid-url', default='http://localhost:8070',
                        help='URL of the running GROBID server')
    args = parser.parse_args()
    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(message)s',
                        level=logging.INFO)

    pdf_files = os.listdir(args.in_dir)
    pdf_files = [f for f in pdf_files if f.endswith('.pdf')]

    logging.info(f'Processing {len(pdf_files)} PDF files.')
    logging.info(f'Input directory:  {args.in_dir}')
    logging.info(f'Output directory: {args.out_dir}')

    # Grobid server needs to be running on Docker
    for i, pdf_file in enumerate(pdf_files):
        pdf_file = os.path.join(args.in_dir, pdf_file)
        process_pdf(pdf_file, args.out_dir, args.grobid_url)
        if i % 100 == 0:
            logging.info(f'Processed {i+1} files.')

    logging.info(f'PDF to XML conversion done.')

if __name__ == '__main__':
    main()
