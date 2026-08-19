# Earthquake Ontologyツール利用ガイド

[English](USER_GUIDE.en.md) | [README](../README.md)

## 1. 概要

本ツールは、外部機関が公開する地震データを取得し、共通モデルを介してEarthquake
Ontology準拠のRDF/Turtleへ変換します。取得原本は上書きせず、SHA-256ごとの不変な
ディレクトリへ保存します。

| コマンド | 用途 |
| --- | --- |
| `earthquake-data-fetch` | データの発見、取得、原本保存 |
| `earthquake-rdf-convert` | プロバイダー形式からTurtleへの変換 |
| `earthquake-rdf-audit` | 大容量Turtleのストリーム検査 |

## 2. インストール

Python 3.10以上を使用してください。

```bash
git clone https://github.com/hirokiu/earthquake-ontology.git
cd earthquake-ontology
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

```bash
earthquake-data-fetch --help
earthquake-rdf-convert --help
earthquake-rdf-audit --help
```

## 3. データ取得

取得元は[`config/sources.yaml`](../config/sources.yaml)で管理します。まず、ダウンロードせず
取得候補を確認してください。

```bash
earthquake-data-fetch --source jma_daily_hypocenters --list
earthquake-data-fetch --source fdsn_events_usgs --period 2025 --list
```

`--source`と`--period`は複数回指定できます。省略すると、有効な全ソース・全期間が対象に
なるため、初回実行では必ず対象を限定することを推奨します。

```bash
earthquake-data-fetch --source jma_daily_hypocenters --period 20260817
earthquake-data-fetch --source fdsn_events_usgs --period 2025
earthquake-data-fetch --source jshis_ground_motion_flatfile --period v2024
```

取得物は次の場所へ保存されます。

```text
var/raw/{source-id}/{period}/{sha256}/{filename}
var/manifests/{source-id}.json
```

同じURLを再取得すると`ETag`または`Last-Modified`を使用します。内容が変わった場合は新しい
SHA-256ディレクトリへ保存され、過去版は残ります。`--force`は条件付きリクエスト情報を
無視しますが、既存原本を上書きしません。

## 4. RDF変換

すべての変換で`--source-uri`に、入力原本またはAPIリクエストの正式なURIを指定します。
出力ファイルが既に存在する場合は停止し、`--force`を指定した場合だけ置換します。

### 4.1 気象庁日別暫定震源リスト

```bash
earthquake-rdf-convert jma-daily daily-20260817.html daily-20260817.ttl \
  --source-uri https://www.data.jma.go.jp/eqev/data/daily_map/20260817.html
```

日別リストは後日訂正される暫定値です。確定月次カタログと同一スナップショットとして
扱わないでください。

### 4.2 気象庁月次震度データ

取得した`iYYYY.zip`から固定長データファイルを安全な作業ディレクトリへ展開してから変換します。
既定の文字コードはShift_JISです。

```bash
earthquake-rdf-convert jma-intensity i2022.dat i2022.ttl \
  --source-uri https://www.data.jma.go.jp/eqev/data/bulletin/data/shindo/i2022.zip
```

スナップショットメタデータも同時に生成できます。

```bash
earthquake-rdf-convert jma-intensity i2022.dat i2022.ttl \
  --source-uri https://www.data.jma.go.jp/eqev/data/bulletin/data/shindo/i2022.zip \
  --snapshot-output i2022.snapshot.ttl \
  --snapshot-uri https://seismic.balog.jp/snapshot/jma/2022/20260819T000000Z \
  --dataset-uri https://www.data.jma.go.jp/eqev/data/bulletin/shindo.html \
  --graph-uri https://seismic.balog.jp/graph/jma/intensity/2022/20260819T000000Z
```

### 4.3 FDSNイベント（QuakeML）

```bash
earthquake-rdf-convert fdsn-events events-2025.xml events-2025.ttl \
  --source-uri 'https://earthquake.usgs.gov/fdsnws/event/1/query?...'
```

`preferredOriginID`と`preferredMagnitudeID`を優先します。旧IRIS形式の公開IDは、既存LODで
使用しているURI形式へ正規化します。

### 4.4 FDSN観測点（StationXML）

```bash
earthquake-rdf-convert fdsn-stations stations.xml stations.ttl \
  --source-uri 'https://service.earthscope.org/fdsnws/station/1/query?...'
```

全世界の観測点応答は大きいため、`fdsn_stations_earthscope`は既定で無効です。運用用YAMLで
ネットワークや期間を限定したURLを設定してから有効化してください。

### 4.5 J-SHIS強震動フラットファイル

```bash
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip flatfile-v2024.ttl \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip
```

ZIP内の`site_schema.tsv`、`source_schema.tsv`、`smrec_schema.tsv`を読み、K-NET/KiK-net観測点、
震源、主要強震指標を変換します。現在はRDFグラフをメモリに保持するため、約2 GBのフル版では
十分なメモリを確保してください。公開時はDOI `10.17598/NIED.0032`などの出典が必要です。

### 4.6 不正レコード

不正レコードがあると既定では変換を停止します。調査時に限り`--allow-issues`を指定すると、
不正レコードを標準エラーへJSON Linesで出力し、正常レコードだけを書き出します。

```bash
earthquake-rdf-convert fdsn-events input.xml output.ttl \
  --source-uri https://example.org/source.xml --allow-issues
```

無人の公開処理では`--allow-issues`を使用せず、原因を修正してください。

## 5. Turtle検査

```bash
earthquake-rdf-audit output.ttl --require-source
earthquake-rdf-audit output-directory/ --require-source --json
```

終了コードは問題なしが`0`、検出ありが`1`です。`--max-findings 0`で検出数を無制限にできます。
公開前にはRDFパーサーによる構文解析と[`shapes/core.shacl.ttl`](../shapes/core.shacl.ttl)による
SHACL検証も実施してください。

## 6. 設定と認証情報

YAMLには秘密情報を記載しません。環境変数は`EQ_`接頭辞と`__`区切りでYAMLより優先されます。

```bash
export EQ_HTTP__RETRIES=5
export EQ_NIED_USERNAME='registered-user'
export EQ_NIED_PASSWORD='secret'
```

K-NET/KiK-netの認証付き直接取得例は既定で無効です。私用設定で有効化し、資格情報は環境変数から
渡してください。別設定は`--config`で指定できます。

```bash
earthquake-data-fetch --config config/production.yaml --source nied_knet_example
```

## 7. 更新・公開運用

外部データは過去分も訂正され得るため、差分SPARQL更新ではなく次の手順を使用します。

1. 原本をSHA-256付きで保存する。
2. 新しい全件RDFとスナップショットを生成する。
3. Turtle構文、監査、SHACLを検証する。
4. 運用中の名前付きグラフをバックアップする。
5. 対象グラフを全件置換する。
6. 新旧スナップショットの来歴を記録する。

詳細は[`data-lifecycle.md`](data-lifecycle.md)を参照してください。

## 8. 開発者向け検証

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

`var/`と`tmp/`はGit管理対象外です。外部機関の利用条件、ライセンス、引用要件はデータソース
ごとに確認してください。
