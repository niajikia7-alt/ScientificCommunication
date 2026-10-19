import argparse

import spacy
import polars as pl
import lftk

if __name__ == '__main__':
    argumentparser = argparse.ArgumentParser()
    # add data path
    argumentparser.add_argument('--data_path', required=True, help="Path to the dataset")
    # add the column name of text
    argumentparser.add_argument('--text_column', required=True, help="Name of the text column")
    # add the output path
    argumentparser.add_argument('--output_path', required=True, help="Path to save the extracted features")
    # add data tpye (options are 'csv' or 'parquet')
    argumentparser.add_argument('--data_type', required=True, help="Type of the dataset")
    argumentparser.add_argument('--chunk_size', type=int, default=10000,
                                help="Number of texts to extract features for at a time")
    args = argumentparser.parse_args()
    feature_groups = ["readtimeformula", "lexicalvariation", "wordsent"]

    nlp = spacy.load("en_core_web_md", disable=["parser", "ner"])
    nlp.add_pipe('sentencizer')
    from tqdm import tqdm


    if args.data_type == 'csv':
        df = pl.read_csv(args.data_path)
    else:
        df = pl.read_parquet(args.data_path)
   # df = df.sample(1000)
    print("columns in the dataframe: ", df.columns)
    print("processing a dataframe of shape %s" % str(df.shape))
    all_feats = []
    for feat_family in feature_groups:
        print("Searching features in family: %s" % feat_family)
        searched_features = lftk.search_features(family=feat_family, language="general", return_format="list_key")
        all_feats.extend(searched_features)

    print("Number of features to be extracted: %d" % len(all_feats))
    print(all_feats)
    docs = tqdm(
        nlp.pipe(df[args.text_column].to_pandas(), batch_size=1000, n_process=-1),
        total=len(df),
        desc="Processing texts"
    )
    # Extract features chunk by chunk, so that only `chunk_size` spaCy docs
    # are held in memory at a time (one row of features per doc)
    extracted_feats = []
    chunk = []
    for doc in docs:
        chunk.append(doc)
        if len(chunk) == args.chunk_size:
            extracted_feats.extend(lftk.Extractor(docs=chunk).extract(features=all_feats))
            chunk = []
    if chunk:
        extracted_feats.extend(lftk.Extractor(docs=chunk).extract(features=all_feats))

    # Convert directly to a Polars DataFrame with correct column names
    extracted_pl = pl.DataFrame(extracted_feats, schema=all_feats)
    print("Extracted features shape: ", extracted_pl.shape)
    # Join with original df (excluding the text column)
    features = df.select(pl.exclude(args.text_column)).hstack(extracted_pl)
    print("Final feature dataframe shape: ", features.shape)

    # Save to parquet
    features.write_parquet(args.output_path)
    print("Features extracted and saved successfully")
