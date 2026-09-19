# AutoLISP PCAP Diamond Electrode Generator

> **Experimental software / 實驗性程式**
>
> This project is under active validation. Its point-generated geometry has
> been regression-checked, but command interaction and final `FILLET` / `CHAMFER`
> behavior still require verification in AutoCAD or BricsCAD. Do not use the
> generated drawing directly for production or fabrication.
>
> 本專案仍在驗證階段。點對點幾何已完成回歸比對，但指令互動與最後的
> `FILLET`／`CHAMFER` 行為仍須在 AutoCAD 或 BricsCAD 實機確認；產出圖面
> 不可未經工程與製程審查就直接用於量產或加工。

A parameterized AutoLISP tool that creates a complete two-layer projected-capacitive (PCAP) diamond-sensor layout: electrodes, conductive fan-out, laser-isolation paths and FPC pin guides.

這是一個參數化 AutoLISP 工具，用來產生雙層投射式電容菱形感測器、周邊導線、雷射隔離線與 FPC pin 輔助線。

## Scope

The project creates editable CAD geometry for early layout, education and visualization. It does **not** calculate capacitance, electric fields, optical visibility, impedance, manufacturability or controller compatibility. It is not a fabrication-ready sensor design.

本專案只產生可編輯的CAD幾何，適合早期配置、教學與視覺化；不計算電容、電場、光學可視性、阻抗、製程能力或控制器相容性，也不能直接作為量產設計。

## Features

- Independent TX/RX pitch and channel counts
- Configurable electrode gap, neck width, route spacing and FPC pin pitch
- Interactive RX and TX pin-bank placement
- Complete Top/Bottom ITO electrode geometry
- Complete Top/Bottom Ag fan-out
- Complete Top/Bottom laser-isolation paths
- Deterministic geometry; the same parameters no longer change with `CDATE`
- Zero-length entities are rejected
- No temporary cache layer, whole-drawing `ssget`, `PEDIT/JOIN`, or `ZOOM`

## Usage

1. Load `pcap-diamond-generator.lsp` with AutoCAD `APPLOAD`.
2. Run `PCAPSENSOR`.
3. Enter the sensor parameters, or press Enter for the documented defaults.
4. Select the RX and TX pin-bank center points.
5. Pick once more when prompted to start generation (legacy-compatible workflow).

Generated layers:

- `Top ITO`
- `Top Ag`
- `Top laser`
- `Bottom ITO`
- `Bottom Ag`
- `Bottom laser`

All repeated geometry is emitted directly from calculated points. The generator avoids the legacy temporary-layer/global-selection cycle that made larger layouts slow. A point-replay regression test confirms that all 1,439 effective LINE entities retain the same layer and endpoint coordinates as the legacy reference case; only three zero-length Ag entities were removed.

Default pitch is 5 mm. It is only an editable starting point, not a production recommendation.

## Reference drawing

The checked reference uses TX 10, RX 6, 5-unit pitch, 1.0 neck, 0.6 gap, 0.1 route spacing and 0.8 pin pitch:

- [`pcap-sensor-corrected-preview.png`](pcap-sensor-corrected-preview.png)
- [`pcap-sensor-electrodes-preview.png`](pcap-sensor-electrodes-preview.png)
- [`pcap-sensor-ag-routing-preview.png`](pcap-sensor-ag-routing-preview.png)
- [`pcap-sensor-laser-preview.png`](pcap-sensor-laser-preview.png)
- `pcap-sensor-corrected-preview.dxf` is generated locally and intentionally ignored by Git.

Regenerate both files without AutoCAD:

```bash
python tools/render_lsp_preview.py
```

The renderer executes the coordinate/math subset used by this LSP and writes
the resulting LINE entities directly. AutoCAD/BricsCAD remains the final host
for checking command interaction, `FILLET` and `CHAMFER` behavior.

## Public references

- [Texas Instruments CapTIvate design guide](https://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/CapTIvate_Design_Center/latest/exports/docs/users_guide/html/CapTIvate_Technology_Guide_html/markdown/ch_design_guide.html)
- [Projected capacitive touch sensing, US20110096025A1](https://patents.google.com/patent/US20110096025A1/en)
- [Diamond patterned touch sensor, US9746964B2](https://patents.google.com/patent/US9746964B2/en)

Patent publications are cited as technical background, not as a patent-clearance opinion. Anyone using this project commercially should perform an independent freedom-to-operate and engineering review.

## Privacy and provenance

This repository contains a public modernization of a user-owned personal utility, generic defaults and synthetic reference coordinates. It contains no employer/customer production drawing, proprietary stack-up, customer identifier or historical source file.

## License

MIT
