"""
CLI Script for running automated display measurements
"""


def main():
    """
    CLI Script for running automated display measurements
    """

    import argparse
    from pathlib import Path

    import numpy as np
    from specio._device_implementations.colorimetry_research import (
        colorimetry_research as cr,
    )
    from specio.serialization import CSMF_Data, CSMF_Metadata, save_csmf_file
    from specio.spectrometers import VirtualSpectrometer

    from ole.ETC.analysis import ColourPrecisionAnalysis
    from ole.measurement_controllers import (
        DisplayMeasureController,
        ProgressPrinter,
    )
    from ole.test_colors import (
        PQ_TestColorsConfig,
        generate_colors,
    )
    from ole.tpg_controller import TPGController
    from ole.utilities import datetime_now

    program_description = """
    Analyze a display for colorimetric linearity and accuracy. This program does
    not specifically evaluate a display's adherence to a particular color
    standard but rather it's color-accuracy relative to the native color space.

    If the display performs well on these metrics, then simple 3x3 transformations
    can reasonably correct for other types of observers such as cameras. It also
    indicates a level of consistent control for the display electronics, accounting
    for small electrical effects that can create large accuracy issues.

    Requires display to be in PQ / native gamut.

    This program will try to automatically discover a connected CR-300 / CR-250
    """
    parser = argparse.ArgumentParser(
        prog="ETC Display Measurements", description=program_description
    )

    parser.add_argument(
        "--device-index",
        default=0,
        help="The DeckLink device index. Default=0",
        required=False,
        type=int,
    )

    parser.add_argument(
        "--warmup",
        default=10,
        help=(
            "The warmup time, in minutes, to show random colors before starting "
            "measurements (helps stabilize temperature). Default=10"
        ),
        required=False,
        type=float,
    )

    parser.add_argument(
        "--stabilization-time",
        default=5,
        help=(
            "The time, in seconds, to show random colors before in between "
            "measurements (helps stabilize LED junction temperature). Default=5"
        ),
        required=False,
        type=float,
    )

    parser.add_argument(
        "--max-luminance",
        default=1500,
        help="The display max luminance in cd/m² (nits), typically as advertised. Default=1500",
        required=False,
        type=float,
    )

    parser.add_argument(
        "--min-above-black",
        default=0.1,
        help=(
            "PQ image signals can get very dark, this sets the minimum "
            "measurable value. Should be based on the in-situ capabilities of "
            "your spectrometer. It's recommended to leave this alone. Default=0.1"
        ),
        required=False,
        type=float,
    )

    parser.add_argument(
        "--bit-depth",
        default=None,
        help=(
            "The bit depth used for the test colors list. "
            "When omitted, auto-detected from the DeckLink device's pixel format."
        ),
        required=False,
        type=int,
    )

    parser.add_argument(
        "--grey-n",
        default=25,
        help="The number of samples to measure in a single grey scale. Default=25",
        required=False,
        type=int,
    )

    parser.add_argument(
        "--cube-n",
        default=8,
        help=(
            "The number of samples to measure in a colour cube. This ads n^3 "
            "measurements, large values will require a very long time to "
            "measure. Default=8"
        ),
        required=False,
        type=int,
    )

    parser.add_argument(
        "--black-n",
        default=20,
        help=(
            "The number of samples to measure in video black. This helps with "
            "analyzing the noise in the spectral measurement. Default=20"
        ),
        required=False,
        type=int,
    )

    parser.add_argument(
        "--white-n",
        default=5,
        help=(
            "The number of samples to measure in video white. Helps with "
            "estimating the display's color primary matrix. Default=5"
        ),
        required=False,
        type=int,
    )

    parser.add_argument(
        "--random",
        default=100,
        help="The number of random test colors to include. Default=100",
        required=False,
        type=int,
    )

    parser.add_argument(
        "--use-virtual",
        action="store_const",
        help="Set to flag to use virtual spectrometer (for debugging TPG)",
        const=-1,
        required=False,
    )

    parser.add_argument(
        "--measurement-speed",
        choices=[
            *zip(
                *[
                    v.values
                    for v in cr.CRSpectrometer.MeasurementSpeed.__members__.values()
                ],
                strict=False,
            )
        ][2],
        help='The number of random test colors to include. Default="Normal"',
        default="normal",
    )

    default_path = "./"

    parser.add_argument(
        "--save-directory",
        help=f"Location to save measurement files. Default = {default_path}",
        default=default_path,
        required=False,
        type=str,
    )

    parser.add_argument(
        "--save-file",
        help="Name of save file. Default = 'DisplayMeasurements_YYMMDD_HHMM",
        default=datetime_now().strftime("Display_Measurements_%y%m%d_%H%M"),
        required=False,
        type=str,
    )

    parser.add_argument(
        "--device-name",
        help=(
            "A name / metadata string that will be embedded in the file. Used "
            "later to determine the header of the ETC Calibration Precision Report"
        ),
        default=datetime_now().strftime("Device Measurements %y-%m-%d %H:%M"),
        required=False,
        type=str,
    )

    args = parser.parse_args()

    with TPGController(device_index=args.device_index) as tpg:
        bit_depth = args.bit_depth if args.bit_depth is not None else tpg.bit_depth

        tcc = PQ_TestColorsConfig(
            ramp_samples=args.grey_n,
            ramp_repeats=1,
            mesh_size=args.cube_n,
            blacks=args.black_n,
            whites=args.white_n,
            random=args.random,
            quantized_bits=bit_depth,
            first_light=args.min_above_black,
            max_luminance=args.max_luminance,
        )
        test_colors = generate_colors(tcc)

        if args.use_virtual == -1:
            meter = VirtualSpectrometer()
        else:
            meter = cr.CRSpectrometer.discover()
            meter.measurement_speed = cr.CRSpectrometer.MeasurementSpeed(
                args.measurement_speed
            )

        dmc = DisplayMeasureController(
            tpg=tpg,
            cr=meter,
            color_list=test_colors,
            progress_callbacks=[ProgressPrinter()],
            max_color_value=tcc.quantized_range,
        )
        dmc.random_colors_duration = args.stabilization_time

        save_path = Path(args.save_directory, args.save_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path = save_path.with_suffix(".csmf")

        measurements = dmc.run_measurements(warmup_time=args.warmup * 60)

        tpg.send_color((0, 0, 0))

    csmf_data = CSMF_Data(
        test_colors=test_colors.colors,
        order=test_colors.order.tolist(),
        measurements=np.asarray(measurements),
        metadata=CSMF_Metadata(notes=args.device_name),
    )

    try:
        data_analysis = ColourPrecisionAnalysis(csmf_data)
        print(data_analysis)
    except Exception as e:
        save_csmf_file(str(save_path.resolve()), ml=csmf_data)
        raise RuntimeError(
            f"Failed to analyze measurements. Saving file to: {save_path:s}"
        ) from e

    save_csmf_file(str(save_path.resolve()), ml=csmf_data)

    print(f"File Saved to: {save_path:s}")


if __name__ == "__main__":
    main()
