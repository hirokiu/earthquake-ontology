# Earthquake Ontologyツール利用ガイド

[English](USER_GUIDE.en.md) | [README](../README.md)

## 1. 概要

本ツールは、外部機関が公開する地震データを取得し、共通モデルを介してEarthquake
Ontology準拠のRDF/Turtleへ変換します。取得原本は上書きせず、SHA-256ごとの不変な
ディレクトリへ保存します。

| コマンド | 用途 |
| --- | --- |
| `earthquake-data-fetch` | データの発見、取得、原本保存 |
| `earthquake-data-organize` | 既存データを作成日別に整理 |
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

出力パスを省略すると、ローカル日付または`--created-at`で指定した日付を使い、次の場所へ
自動保存します。

```text
data/YYYY-MM-DD/{変換サブコマンド}/{出力形式}/{入力ファイル名}.{拡張子}
```

自動生成されるファイル名には、フォルダを見なくても判別できるように提供元とデータ種別が
含まれます。例：`usgs-fdsn-events-1960.nq`、
`jma-daily-hypocenters-20260817.ttl`。

```bash
earthquake-rdf-convert fdsn-events events-2025.xml \
  --source-uri 'https://earthquake.usgs.gov/fdsnws/event/1/query?...' \
  --output-format ntriples --created-at 2026-08-19
```

`--output-format`は`turtle`、`ntriples`、`nquads`から選択できます。`nquads`では
`--graph-uri`が必須です。

`--split-by-entity`を指定すると、混在ファイルの代わりに`*-hypocenters`（震源）、
`*-stations`（観測点）、`*-observed-waves`（観測波形・強震記録）の3種類へ分割します。
各観測網で共通して、震源決定機関はURI値の`jpe:detarminatedBy`、決定方法や原本フラグは
`jpe:determinatedWay`で表します。既知の機関には公式URIを使用し、未知の機関コードにも
安定したローカルURIを割り当てます。

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

`fdsn_stations_earthscope`は全世界のstationレベルStationXMLを取得します。必要に応じて
運用用YAMLでネットワークや期間を限定してください。

### 4.5 気象庁震度観測点

`code_p.zip`を基本データとし、公式の詳細一覧HTMLを指定すると所在地と地域名称も統合します。
観測点URIは月次震度観測レコードの`jpe:observedBy`と一致します。

```bash
earthquake-rdf-convert jma-stations code_p.zip \
  --source-uri https://www.data.jma.go.jp/eqev/data/bulletin/data/shindo/code_p.zip \
  --details-html jma-shindo-current.html \
  --details-source-uri https://www.data.jma.go.jp/eqev/data/kyoshin/jma-shindo.html \
  --split-by-entity --enrich-addresses
```

### 4.6 J-SHIS強震動フラットファイル

```bash
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip flatfile-v2024.ttl \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip
```

全体ファイルに加えて地震発生年ごとのファイルを作る場合は`--split-by-year`を指定します。
例えば出力が`flatfile-v2024.ttl`なら、同じ場所に`flatfile-v2024-1996.ttl`のような
年別ファイルを生成します。各年版には、その年の震源、関連する強震記録、およびそれらが参照する
観測点が含まれます。

```bash
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip \
  --split-by-year --split-by-entity --enrich-addresses
```

`--split-by-year`と`--split-by-entity`を併用すると、全期間版と各年版の双方を3種類の
エンティティ別ファイルとして生成します。

日時は`xsd:dateTime`としてタイムゾーン付きで出力します。気象庁とJ-SHISの日時は日本標準時
（例：`2024-01-02T03:04:05+09:00`）、FDSN/QuakeMLは入力のオフセットを保持し、`Z`は
`+00:00`として出力します。タイムゾーンのない日時はモデル層で拒否されます。

ZIP内の`site_schema.tsv`、`source_schema.tsv`、`smrec_schema.tsv`を読み、K-NET/KiK-net観測点、
震源、主要強震指標を変換します。現在はRDFグラフをメモリに保持するため、約2 GBのフル版では
十分なメモリを確保してください。公開時はDOI `10.17598/NIED.0032`などの出典が必要です。

### 4.7 不正レコード

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

## 6. QLeverへの投入

QLeverの`qlever index`が直接受け付けるTurtle（`ttl`）、N-Triples（`nt`）、N-Quads（`nq`）に
対応しています。名前付きグラフを維持する場合はN-Quadsを使用します。

```bash
earthquake-rdf-convert fdsn-events events-2025.xml \
  --source-uri 'https://earthquake.usgs.gov/fdsnws/event/1/query?...' \
  --output-format nquads \
  --graph-uri https://seismic.balog.jp/graph/fdsn/usgs/2025/20260819

qlever index --format nq \
  --input-files 'data/2026-08-19/fdsn-events/nquads/*.nq'
```

大量データの初回投入や全件更新では、SPARQL `INSERT DATA`ではなくインデックス再構築を使用します。

## 7. 既存dataディレクトリの整理

実行前に移動計画を確認し、`--apply`で適用します。ファイルの作成日時が利用できない環境では
更新日時を使用します。移動対応表は`data/_manifests/`に保存されます。

```bash
earthquake-data-organize --root data
earthquake-data-organize --root data --apply
earthquake-data-organize --root data --normalize-names
earthquake-data-organize --root data --normalize-names --apply
```

`--normalize-names`は、既存ファイル名へ`jma-`、`fdsn-`、`knet-`、`aist-`などの提供元を
表す接頭辞を付けます。名前変更の対応表も`data/_manifests/`へ保存されます。

## 8. 設定と認証情報

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

## 9. 更新・公開運用

外部データは過去分も訂正され得るため、差分SPARQL更新ではなく次の手順を使用します。

1. 原本をSHA-256付きで保存する。
2. 新しい全件RDFとスナップショットを生成する。
3. Turtle構文、監査、SHACLを検証する。
4. 運用中の名前付きグラフをバックアップする。
5. 対象グラフを全件置換する。
6. 新旧スナップショットの来歴を記録する。

詳細は[`data-lifecycle.md`](data-lifecycle.md)を参照してください。

## 10. 開発者向け検証

### 観測点住所

観測点の原データに住所または行政区画が含まれる場合、次の語彙を同時に出力します。

```turtle
@prefix schema: <http://schema.org/> .
@prefix ic: <http://imi.go.jp/ns/core/rdf#> .

<https://seismic.balog.jp/resource/example-station>
    schema:address "北海道石狩市"@ja ;
    ic:住所 <https://uedayou.net/loa/%E5%8C%97%E6%B5%B7%E9%81%93%E7%9F%B3%E7%8B%A9%E5%B8%82> ;
    ic:都道府県 "北海道"@ja ;
    ic:都道府県コード "01" ;
    ic:市区町村 "石狩市"@ja ;
    ic:市区町村コード "01235" .
```

住所が原データにない場合、観測点名から推測して住所を生成しません。緯度経度から補完する場合は、
`fdsn-stations`または`jshis-flatfile`へ`--enrich-addresses`を指定します。

```bash
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip \
  --enrich-addresses \
  --address-cache var/cache/gsi-addresses.json \
  --address-request-interval 0.2
```

日本付近の座標だけを国土地理院の逆ジオコーダーへ問い合わせ、市区町村コードを公式の
`muni.js`と照合します。既存住所を上書きしません。結果・取得元URI・取得日時は座標単位で
キャッシュされ、同じ座標の再実行ではネットワークへアクセスしません。該当住所がない場合も
`not_found`としてキャッシュします。初回の大量補完では国土地理院へ過度な負荷を与えないよう、
リクエスト間隔を短くしすぎないでください。

取得ミスや行政区画の更新により全件を再取得する場合は、`--clear-address-cache`を
`--enrich-addresses`と同時に指定します。既存キャッシュは
`gsi-addresses.json.backup-{UTCタイムスタンプ}`へ退避されるため復旧可能です。自治体表と
住所検索結果の両方が初期化されます。

```bash
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip \
  --enrich-addresses --clear-address-cache \
  --address-cache var/cache/gsi-addresses.json
```

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

`var/`と`tmp/`はGit管理対象外です。外部機関の利用条件、ライセンス、引用要件はデータソース
ごとに確認してください。
