from ast import literal_eval
from os.path import exists

import pandas as pd
import numpy as np


def aggragate_cells_by_type(grouped_data, cell_dataset_path,
                            chunksize=10000):
    with pd.read_csv(cell_dataset_path, chunksize=chunksize) as reader:
        for i, chunk in enumerate(reader):
            print(f"Processing a chunk {i}...")
            data = chunk.set_index("sample_name")
            print("Length ", data.shape)

            for ttype in grouped_data.index:
                print("\tCollecting cells for ", ttype)

                selected_samples = grouped_data["sample_name"].loc[ttype]

                chuck_sample = [
                    s for s in selected_samples
                    if s in data.index
                ]
                current_cell_data = data.loc[chuck_sample].values

                ttype_filename =\
                    "/gpfs/bbp.cscs.ch/project/proj116/{ttype}_cells.npy"

                file_exists = exists(ttype_filename)
                if file_exists:
                    print("\t\tLoading... ", f"{ttype}_cells.npy")
                    old_cell_data = np.load(ttype_filename)
                    cell_data = np.concatenate(
                        [old_cell_data, current_cell_data])
                else:
                    cell_data = current_cell_data

                print("\t\tSaving to... ", f"{ttype}_cells.npy")
                np.save(
                    f"/gpfs/bbp.cscs.ch/project/proj116/{ttype}_cells.npy",
                    cell_data)


if __name__ == '__main__':
    cell_dataset_path =\
        "/gpfs/bbp.cscs.ch/project/proj116/allen_cell_expression.csv"

    grouped_data = pd.read_csv(
        "/gpfs/bbp.cscs.ch/project/proj116/grouped_meta_data.csv").set_index(
        "cell_type_accession_label")[["sample_name"]]
    for c in grouped_data.columns:
        print(c)
        grouped_data[c] = grouped_data[c].apply(literal_eval)

    aggragate_cells_by_type(
        grouped_data, cell_dataset_path)
