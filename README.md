# MasterThesisTemplate-JoaoSimao

This repository holds all the test templates used in my thesis, together with the
supporting data, analysis code, and outputs.

## Overview

The tests are built in a **modular** way: each test pulls its data from a clearly
defined source, so you can try them out with your own data simply by changing where
the test reads from.

- **ASAP 2.0** public data is included. The original dataset is available at
  [github.com/scrosseye/ASAP_2.0](https://github.com/scrosseye/ASAP_2.0) and is
  provided under the Attribution 4.0 International (CC BY 4.0)
  [license](https://creativecommons.org/licenses/by/4.0/).
- **IAVE** data is **not** included, as it is confidential. However, the **IAVE
  questions themselves are provided** (see `IAVEQuestions.txt`) for reference.

## Repository Structure

| Path | Description |
|------|-------------|
| `ASAP2.0/` | Test templates and ASAP 2.0 public data. |
| `Dataset/` | Datasets used by the tests. |
| `longdataformat/` | ASAP data in long data format. |
| `Visuais/` | Code used to generate the figures for the thesis. |
| `asap_analysis.R` | R code used to evaluate the long data format. |
| `GradingOutputsCSVs.zip` | All grading outputs for ASAP (CSV files). |
| `IAVEQuestions.txt` | The IAVE questions (the IAVE data itself is confidential). |

## Usage

1. Pick the test template you want to run from `ASAP2.0/`.
2. To use your own data, point the test at your data source, the modular design
   makes this a one-line change.
3. Use `asap_analysis.R` to evaluate data in the long data format.
4. Grading outputs for ASAP are available in `GradingOutputsCSVs.zip`.

## License & Attribution

The ASAP 2.0 data is provided under the Attribution 4.0 International (CC BY 4.0)
[license](https://creativecommons.org/licenses/by/4.0/). Source:
[github.com/scrosseye/ASAP_2.0](https://github.com/scrosseye/ASAP_2.0).

## Contact

Any questions or need for further explanation, please feel free to contact me.
