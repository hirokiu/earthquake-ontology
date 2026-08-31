# QLever SPARQL投入・照会試験

- 実行日: 2026-08-31
- QLever server build: `5799024`
- QLever CLI: `0.6.0`
- 隔離エンドポイント: `http://127.0.0.1:7026`
- graph: `https://seismic.balog.jp/graph/jma/named-earthquakes/20260831`
- 投入方式: SPARQL 1.1 `INSERT DATA`
- update処理時間: 37 ms

## 結果

| 検査 | 期待 | 実測 | 結果 |
|---|---:|---:|---|
| グラフトリプル | 285 | 285 | PASS |
| 命名地震活動 | 34 | 34 | PASS |
| 単一地震型 | 29 | 29 | PASS |
| 一連活動型 | 3 | 3 | PASS |
| 群発地震型 | 1 | 1 | PASS |
| 遠地地震・津波型 | 1 | 1 | PASS |
| 災害事例 | 3 | 3 | PASS |
| 能登開始 | 2020-12 | 2020-12 | PASS |
| 能登の未確認subEvent | 0 | 0 | PASS |
| Membership | 0 | 0 | PASS |
| 確定包含関係 | 0 | 0 | PASS |
| 地震活動altLabelへの「大震災」混入 | 0 | 0 | PASS |

本番JMA震源カタログをまだ指定していないため、この投入物は命名地震メタデータのみであり、
Membershipが0件なのは意図した結果である。
