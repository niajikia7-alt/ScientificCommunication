import argparse
import os
import pandas as pd


def extend_metadata(papers_df: pd.DataFrame, anthology_df: pd.DataFrame) -> pd.DataFrame:
    """Adds Anthology BIB metadata based on `acl_id`."""
    df = papers_df.merge(anthology_df, how='left', on='acl_id')

    # For papers with empty title (e.g. XML parsing issues), use BIB title
    df['title'] = df.apply(
        lambda x: x.title_x if not x.title_x == '' else x.title_y, axis=1
    )
    df = df.drop(columns=['title_x', 'title_y'])
    return df


def main():
    desc = 'Extends papers dataframe (based on XML content) by adding info '\
           'from ACL anthology BIB.'
    fmt = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(description=desc, formatter_class=fmt)
    parser.add_argument('papers_df', help='DF with paper content from XML')
    parser.add_argument('out_file', help='file where to dump full DF')
    parser.add_argument('--anthology', help='Anthology DF',
                        default='anthology.parquet')
    parser.add_argument('--overwrite', action='store_true',
                        help='replace the output file if it already exists')
    args = parser.parse_args()

    if os.path.isfile(args.out_file) and not args.overwrite:
        raise SystemExit(f'Output file already exists: {args.out_file} '
                         '(use --overwrite to replace it)')

    papers_df = pd.read_parquet(args.papers_df)
    anthology_df = pd.read_parquet(args.anthology)
    full_df = extend_metadata(papers_df, anthology_df)
    full_df.to_parquet(args.out_file)
    print(f'Wrote {len(full_df)} papers to {args.out_file}')

if __name__ == '__main__':
    main()