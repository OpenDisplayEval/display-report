def main():
    import argparse
    from pathlib import Path

    from specio.serialization import CSMF_Metadata, load_csmf_file, save_csmf_file

    from display_report.utilities import get_valid_filename

    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="The csmf file to strip data from")

    parser.add_argument("-o", "--out-dir", help="Output directory", default=None)

    args = parser.parse_args()

    file_path = Path(args.file)
    file_data = load_csmf_file(file_path)

    output_path = file_path.parent if args.out_dir is None else Path(args.out_dir)

    file_data.metadata = CSMF_Metadata(software="colour-workbench file stripper")

    output_path = output_path.joinpath(
        get_valid_filename(file_data.shortname)
    ).with_suffix(".csmf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving anonymized data: {output_path!s} <- {file_path!s}")

    save_csmf_file(file=str(output_path), ml=file_data)


if __name__ == "__main__":
    main()
