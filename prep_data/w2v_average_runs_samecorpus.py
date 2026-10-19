"""This script takes multiple w2v models trained on the same corpus and
builds a similarity matrix for the whole vocabulary by averaging over
the similarities from all models."""
import argparse
import numpy as np
import os
import pandas as pd
from itertools import combinations
from gensim.models import Word2Vec
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_files', nargs='+', help='gensim word2vec models '
                        'whose similarities will be averaged together; they '
                        'must have identical vocabularies')
    parser.add_argument('out_dir', help='output directory to write out average '
                        'similarity matrix as pandas parquet file')
    parser.add_argument('--out_file', help='output file name; if not provided, '
                        'defaults to {model_files[0]}_sim_avg.parquet')
    parser.add_argument('--smaller', action='store_true', default=False,
                        help='saves output in np.float16 format')
    parser.add_argument('--block_size', type=int, default=2000,
                        help='rows per block when computing similarities')
    args = parser.parse_args()

    # Load individual models
    models = []
    vocabs = []
    for model_file in args.model_files:
        model = Word2Vec.load(model_file)
        models.append(model.wv.get_normed_vectors())
        vocabs.append(model.wv.index_to_key)
        print('Model loaded:', model_file)

    # Check that vocabularies are identical
    for vocab1, vocab2 in combinations(vocabs, 2):
        if vocab1 != vocab2:
            raise ValueError('Vocabularies not identical')
    print('All vocabularies identical.')

    # Get average similarity matrix, accumulated in row blocks so that only
    # one vocabulary-sized matrix is held in memory regardless of run count
    n = len(vocabs[0])
    mean_matrix = np.zeros((n, n), dtype=np.float32)
    for model in models:
        for start in range(0, n, args.block_size):
            end = start + args.block_size
            mean_matrix[start:end] += np.dot(model[start:end], model.T)
    mean_matrix /= len(models)
    print('Mean similarity matrix computed.')
    if args.smaller:
        mean_matrix = mean_matrix.astype(np.float16)
        print('Saving in np.float16')

    # Put everything into pandas and write out
    df = pd.DataFrame(mean_matrix, index=vocabs[0], columns=vocabs[0])
    if not args.out_file:
        args.out_file = f'{Path(args.model_files[0]).stem}_sim_avg.parquet'
    out_path = os.path.join(args.out_dir, args.out_file)
    df.to_parquet(out_path)
    print('Output written:', out_path)

if __name__ == '__main__':
    main()