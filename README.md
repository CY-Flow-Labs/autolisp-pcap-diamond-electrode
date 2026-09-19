# AutoLISP PCAP Diamond Electrode Generator

A small, parameterized AutoLISP tool that creates a generic interleaved TX/RX diamond-electrode lattice for projected-capacitive (PCAP) mutual-capacitance exploration.

這是一個參數化AutoLISP小工具，用來產生通用的投射式電容菱形電極示意格網。

## Scope

The project creates editable CAD geometry for early layout, education and visualization. It does **not** calculate capacitance, electric fields, optical visibility, impedance, manufacturability or controller compatibility. It is not a fabrication-ready sensor design.

本專案只產生可編輯的CAD幾何，適合早期配置、教學與視覺化；不計算電容、電場、光學可視性、阻抗、製程能力或控制器相容性，也不能直接作為量產設計。

## Features

- Independent horizontal and vertical pitch
- Configurable TX rows and RX columns
- Configurable diamond gap and connector width
- Separate TX, RX and connector layers
- Reusable diamond block references for faster large-array generation
- One Undo group for every generated lattice
- Input validation and AutoCAD state restoration
- No temporary global-selection layer

## Usage

1. Load `pcap-diamond-generator.lsp` with AutoCAD `APPLOAD`.
2. Run `PCAPDIAMOND`.
3. Select the lower-left origin.
4. Enter channel counts, pitch, gap and connector width, or accept the defaults.

Generated layers:

- `PCAP_TX_ELECTRODE`
- `PCAP_RX_ELECTRODE`
- `PCAP_TX_INTERCONNECT`
- `PCAP_RX_INTERCONNECT`

Diamonds are stored as lightweight block references. Identical dimensions reuse the same block definition, reducing repeated vertex data and keeping larger drawings responsive. Connectors are created directly with DXF entities; the generator does not run `PEDIT`, `JOIN`, `FILLET`, `CHAMFER`, `ZOOM` or whole-drawing selection inside its loops.

Default pitch is 5 mm. It is only an editable starting point, not a production recommendation.

## Design model

TX diamonds form horizontal chains. RX diamonds form vertical chains offset by one pitch in both axes. The conductors are separated into dedicated CAD layers to represent a generic two-layer layout. Edge routing, tail design, bridges, shielding and fabrication compensation are intentionally outside this project.

## Public references

- [Texas Instruments CapTIvate design guide](https://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/CapTIvate_Design_Center/latest/exports/docs/users_guide/html/CapTIvate_Technology_Guide_html/markdown/ch_design_guide.html)
- [Projected capacitive touch sensing, US20110096025A1](https://patents.google.com/patent/US20110096025A1/en)
- [Diamond patterned touch sensor, US9746964B2](https://patents.google.com/patent/US9746964B2/en)

Patent publications are cited as technical background, not as a patent-clearance opinion. Anyone using this project commercially should perform an independent freedom-to-operate and engineering review.

## Privacy and provenance

This repository contains newly written generic geometry code and synthetic defaults. It contains no employer, customer or production drawing; no proprietary stack-up; and no historical source file.

## License

MIT
