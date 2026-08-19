# オントロジー・スキーマ確認メモ

## 1. 目的と調査範囲

この文書は、2026年8月のデータ取得・RDF変換基盤の追加に伴うオントロジーとSHACLの変更を
確認するためのメモである。比較元は`ISWC2026`の復元点`b14ded550`、確認対象は現在の`dev`
ブランチである。次を照合した。

- `ontology/jp-earthquake.ttl`
- `shapes/core.shacl.ttl`
- JMA年次震度・震源固定長データと日別暫定震源データ
- USGS FDSN Event QuakeMLとFDSN StationXML
- J-SHIS地震ハザードステーション強震動フラットファイルv2024
- Pythonの共通モデル、各パーサー、RDFビルダー
- 2026-08-19に実際に生成したTurtle

「オントロジー」はOWL/RDFSによる語彙定義、「スキーマ」はSHACL制約として区別する。
`schema:`、`sosa:`、`prov:`、`dcat:`、`ic:`は外部語彙であり、本オントロジー独自語彙ではない。

## 2. 今回新規に追加したクラス

|語彙|意味|追加理由|主な元データ・運用要件|現在の利用状況|
|---|---|---|---|---|
|`jpe:DatasetSnapshot`|外部データを取得時点ごとに固定したRDF版|原本が過去に遡って更新されるため、バックアップ後の全件更新と版管理を可能にする|取得日時、原本SHA-256、データセットURI、名前付きグラフURI|CLIのスナップショット出力で利用可能。今回の通常変換データには未付与|
|`jpe:StrongMotionRecord`|観測点に紐づく強震記録および主要指標|J-SHISの`smrec_schema.tsv`を、単なる震度観測とは分けて表現するため|J-SHIS `smrec_id`、`filebasename`、PGA、PGV、SI値など|J-SHIS全体版・年別版で使用|

既存の`jpe:earthquake`、`jpe:hypocenter`、`jpe:epicenter`、`jpe:observer`、
`jpe:seismicMotion`、`jpe:observedWave`は新規追加ではない。ただし、従来の個体のような宣言を
OWLクラスへ整理し、`schema:`やSOSAとの上位クラス関係、日英ラベル、domain/rangeを明確化した。

## 3. 今回新規に追加した独自プロパティ

### 3.1 震源・観測・識別

|語彙|型・値|追加理由|元データ|実データでの利用|
|---|---|---|---|---|
|`jpe:catalog`|文字列|採用された震源の提供カタログ・機関を保持する|FDSN `origin/creationInfo/agencyID`、JMA日別、J-SHIS|FDSN、JMA日別、J-SHISで使用|
|`jpe:determinatedWay`|文字列|旧綴り`detarminatedWay`を修正し、震源決定方法または原本フラグを統一して格納する|JMA震源決定フラグ、FDSN `evaluationMode` / `methodID`|JMA、FDSNで使用|
|`jpe:detarminatedBy`|IRI（`prov:Agent`）|震源を決定した機関を、決定方法と分離してURI参照可能にする|JMA、J-SHISのJMA震源、FDSN `origin/creationInfo/agencyID`|JMA、J-SHIS、FDSNで使用。既知機関は公式URI、未知コードは安定したローカルURI|
|`jpe:observedStationNum`|非負整数|旧綴り`observedStaionNum`を修正する|JMAの震度1以上観測点数|JMA年次データで使用|
|`jpe:calcShindo`|小数|従来の`seismicIntensity`を明確な計測震度プロパティへ整理する|JMA観測レコードの計測震度|JMA年次データで使用|

### 3.2 J-SHIS強震記録

|語彙|J-SHIS列|単位・値|追加理由|
|---|---|---|---|
|`jpe:recordIdentifier`|`smrec_id`|文字列|強震記録の安定した識別子|
|`jpe:fileBaseName`|`filebasename`|文字列|元波形ファイルとの対応保持|
|`jpe:sampleCount`|`length`|非負整数|波形サンプル数|
|`jpe:samplingFrequency`|`samplefreq`|Hz|サンプリング条件|
|`jpe:peakGroundAccelerationNS`|`maxacc0`|原データの加速度単位|南北成分PGA|
|`jpe:peakGroundAccelerationEW`|`maxacc1`|原データの加速度単位|東西成分PGA|
|`jpe:peakGroundAccelerationUD`|`maxacc2`|原データの加速度単位|上下成分PGA|
|`jpe:peakGroundVelocityNS`|`maxvel0`|原データの速度単位|南北成分PGV|
|`jpe:peakGroundVelocityEW`|`maxvel1`|原データの速度単位|東西成分PGV|
|`jpe:peakGroundVelocityUD`|`maxvel2`|原データの速度単位|上下成分PGV|
|`jpe:spectrumIntensity`|`sival`|原データのSI単位|SI値|
|`jpe:instrumentalIntensity`|`sindo`|小数|J-SHISの計測震度|
|`jpe:faultDistance`|`fault_dist`|km|断層最短距離|

PGA、PGV、SI値は現在のオントロジーに単位の機械可読な定義がない。値の意味を安全に交換するには、
QUDTまたはOM等の単位語彙を採用するか、観測値ノードと単位を分離する設計を検討する必要がある。

### 3.3 スナップショット・出典

|語彙|型・値|追加理由|元データ・運用情報|
|---|---|---|---|
|`jpe:snapshotOf`|オブジェクトプロパティ|RDF版がどの外部データセットの版かを示す|`config/sources.yaml`の`dataset_uri`|
|`jpe:previousSnapshot`|オブジェクトプロパティ|一つ前の版を参照して更新系列を表す|更新処理が管理する直前スナップショットURI|
|`jpe:sourceChecksum`|`xsd:hexBinary`|同じURLの内容変更を識別し、原本を検証する|取得原本のSHA-256|

各リソースには独自語彙を増やさず、標準語彙`prov:wasDerivedFrom`で取得元URIを付与した。
スナップショットには`prov:generatedAtTime`、`dcat:distribution`、`prov:wasRevisionOf`も利用する。

## 4. 新たに採用した外部語彙

|語彙|用途|採用理由|元データ・生成方法|
|---|---|---|---|
|`schema:latitude`、`schema:longitude`|緯度・経度|既存LODとの互換性と一般的な検索性|全データソース|
|`schema:elevation`|観測点標高|観測点属性を独自語彙化しない|J-SHIS、FDSN StationXML|
|`schema:startTime`|観測時刻|観測の開始時刻|JMA震度観測|
|`schema:availabilityStarts`、`schema:availabilityEnds`|観測点運用期間|観測点の有効期間|J-SHIS `start_date`、`end_date`、FDSN StationXML|
|`schema:address`|住所文字列|人が読める住所を広く利用される語彙で表す|元データまたは国土地理院逆ジオコーダー|
|`ic:住所`|住所URI|IMI共通語彙基盤による構造化住所への参照|住所文字列から生成したLOA URI|
|`ic:都道府県`、`ic:都道府県コード`|都道府県名・コード|日本の行政区域を構造化する|国土地理院APIと`muni.js`|
|`ic:市区町村`、`ic:市区町村コード`|市区町村名・コード|日本の行政区域を構造化する|国土地理院APIと`muni.js`|
|`prov:wasDerivedFrom`|リソースの取得元|LODを外部機関データの別形式として追跡可能にする|配布ファイルまたはAPIリクエストURI|

## 5. 新規SHACLスキーマ

`shapes/core.shacl.ttl`自体が今回新設された。

|Shape|対象|主な制約|作成理由|現状評価|
|---|---|---|---|---|
|`jpe:HypocenterShape`|`jpe:hypocenter`|時刻1件、緯度経度1件・範囲、深さ・M最大1件、出典URI推奨|JMA/FDSN/J-SHIS震源の最低限の共通品質|利用可能。ただし深さ・Mのdatatype制約が不足|
|`jpe:ObservedWaveShape`|`jpe:observedWave`|開始時刻、震源、観測点を各1件、計測震度最大1件|JMA観測レコードの参照整合性|JMAには適合。下記の継承問題あり|
|`jpe:StationShape`|`jpe:observer`|識別子、緯度経度、住所文字列・住所IRI最大1件|FDSN/J-SHIS観測点の最低限品質|利用可能。IMI住所内訳の制約は未定義|
|`jpe:DatasetSnapshotShape`|`jpe:DatasetSnapshot`|元データセット、生成日時、SHA-256を各1件|バックアップ・全件更新時の版管理品質|通常生成では未使用。スナップショット生成時のみ対象|

### 5.1 SHACL上の要修正事項

|優先度|問題|影響|推奨対応|
|---|---|---|---|
|対応済み|J-SHIS強震記録には信頼できる観測開始時刻がなく、`observedWave`の必須条件を満たせなかった|震源時刻を観測開始時刻として誤用する危険があった|`StrongMotionRecord`を独立した`sosa:Observation`とし、識別子・震源・観測点を検査する専用Shapeを追加した|
|中|タイムゾーン必須をSHACLだけでは検査していない|`xsd:dateTime`でもタイムゾーンなし字句を許し得る|SHACL-SPARQLまたはパターン制約を追加する。Pythonモデルでは既に必須|
|中|PGA/PGV/SI値にdatatype、単位、最小・最大件数の制約がない|値の単位混在や文字列化を検出できない|単位モデル決定後にShapeへ反映する|
|中|`ic:都道府県コード`等の桁数・NodeKind制約がない|住所コードの誤りを検出できない|都道府県2桁、市区町村5桁等のパターンを検討する|
|低|`jpe:depth`、`jpe:magnitude`のSHACL datatypeが未指定|文字列値が混入しても検出できない|`xsd:decimal`を指定する|

## 6. スキーマまたはモデルがないためTTLへ入っていないデータ

以下は、原本に列・要素が存在するが、共通モデル、独自語彙、または採用する外部語彙が未決定のため
現在のTurtleへ出力していない代表例である。「未変換」は原本アーカイブには保持されている。

### 6.1 J-SHIS v2024

|原本テーブル|未変換列・列群|内容|未変換の主因|拡張候補|
|---|---|---|---|---|
|`site_schema.tsv`|`sensor_depth_glminus`|地表面からのセンサー深度|観測装置・設置位置モデルがない|SOSA/SSNのSensor、Deployment、Platform|
|同上|`installation_situation_id`|設置状況区分|コード表との対応語彙がない|SKOS ConceptScheme|
|同上|`dist_vf_mf13_nejapan`、`dist_vf_mf13_swjapan`|火山フロント等との距離指標|意味・単位を表す語彙が未定|QUDT付き距離観測値|
|同上|`vs10`、`vs20`、`vs30`、`avs30`|表層地盤の平均S波速度|地盤・速度プロファイルモデルがない|GeoSPARQL、SOSA Observation、QUDT|
|同上|`meshcode250`、`meshcode3`|地域メッシュコード|メッシュURI方針がない|標準地域メッシュのURI化|
|同上|`d1100`、`d1400`、`d1700`、`d2100`、`dbase`|速度層・基盤深度|地下構造モデルと単位定義がない|地盤層クラスと深度観測値|
|`source_schema.tsv`|`segment_idx`|断層セグメント番号|震源と断層モデルの関係が未定|Fault、FaultSegmentクラス|
|同上|`nf_origin_time`、`nf_lat`、`nf_lon`、`nf_depth`|別震源解|複数震源解と採用解のモデルがない|OriginSolutionクラスとpreferred関係|
|同上|`mw`|モーメントマグニチュード|現在は`mjma`一値のみをHypocenterへ格納|MagnitudeObservationクラス|
|同上|`strike1`、`dip1`、`rake1`、`eq_mechanism_type_id`|発震機構|発震機構モデルがない|FocalMechanismクラス|
|同上|`cmt_depth`、`varred`、`mxx`～`mzz`、`exp`|CMT・モーメントテンソル|テンソルと単位モデルがない|MomentTensorクラス|
|同上|`width`、`length`、`top_center_lat/lon`、`strike_deg`、`dip_deg`、`h_top`|矩形断層モデル|断層面形状モデルがない|GeoSPARQL GeometryとFaultPlane|
|`smrec_schema.tsv`|`maxaccrd000`～`maxaccrd100`|回転方向別最大加速度|成分・方位を一般化した観測値モデルがない|成分ノード＋方位＋単位|
|同上|`maxvel*_filchb1`、`maxvelrd*`、`maxaccv`、`maxvelv`|フィルター別・回転別・合成最大値|処理条件を表すモデルがない|ProcessingMethodとResult|
|同上|`rsaccc2d005t*`、`rsaccrd*d005t*`|周期・減衰・方位別応答スペクトル|数百列をプロパティ化せず、スペクトル構造を未設計|ResponseSpectrum、period、damping、direction、value|
|同上|`maxsvad005`|最大速度応答値|単位・減衰条件モデルがない|ResponseSpectrum派生値|
|同上|`lower_period`、`upper_period`、`multiple`|処理対象周期・倍率|処理メタデータモデルがない|ProcessingParameter|

### 6.2 FDSN QuakeML / StationXML

|原本要素群|現在の扱い|未変換の主因|拡張候補|
|---|---|---|---|
|複数の`origin`・`magnitude`|preferredのみ採用|Hypocenterに単一値を直接持たせている|OriginSolution、MagnitudeObservationとpreferred関係|
|origin/magnitudeのuncertainty、confidenceLevel|未変換|不確かさモデルがない|SOSA result quality、QUDT uncertainty|
|`quality`、`evaluationMode`、`evaluationStatus`|未変換|品質・レビュー状態の語彙がない|SKOSコード体系|
|pick、arrival、amplitude|未変換|位相到達・波形特徴モデルがない|SOSA Observation、SeismicPhase|
|event type/certainty|未変換|地震種別コード体系がない|EventType ConceptScheme|
|focalMechanism、momentTensor|未変換|J-SHISと共通の発震機構モデルがない|FocalMechanism、MomentTensor|
|creationInfoのversion、creationTime等|agency/authorの一部のみ使用|リソース単位の版・生成主体モデルが未実装|PROV-O|
|StationXMLのChannel、Sensor、DataLogger、Response|Station階層までのみ変換|チャンネル・機器応答モデルがない|SOSA/SSN、FDSN StationXML語彙|
|StationXMLのrestrictedStatus、alternateCode等|未変換|アクセス条件・別名の対応方針がない|dcterms:accessRights、schema:alternateName|

### 6.3 気象庁データ

|原本項目群|現在の扱い|未変換の主因|拡張候補|
|---|---|---|---|
|震源・観測値の誤差、精度、補助フラグ|主要値のみ使用|品質・不確かさモデルがない|QualityMeasure、uncertainty|
|複数のマグニチュード欄・補助コード|主要マグニチュードのみ使用|複数Mと算出法のモデルがない|MagnitudeObservation|
|観測レコードの成分別詳細・補助値|震度と計測震度のみ使用|波形・成分・処理条件モデルがない|StrongMotionRecordとの統合|
|欠損時刻・欠損座標を含む歴史レコード|監査ログへ出力しTTL化しない|現行`HypocenterShape`とPythonモデルが完全な日時・座標を必須とする|不完全歴史資料用クラスまたは精度付き時間・場所モデルを別途検討|

歴史的な気象庁年次データでは、時刻・座標等が不足する185,362件を監査ログへ分離した。
これは単に語彙を追加すれば解決する問題ではなく、「不完全な震源記録」を通常の`jpe:hypocenter`と
同一クラスで公開するかというモデリング判断が必要である。

## 7. 定義済みだが現在の生成データで未使用の語彙・スキーマ

|区分|語彙・Shape|未使用理由|今後の判断|
|---|---|---|---|
|クラス|`jpe:earthquake`|各パーサーは震源を直接生成し、地震現象リソースを別作成していない|地震現象と複数震源解を分離するなら使用|
|クラス|`jpe:epicenter`|震央を震源から独立したリソースにしていない|2次元位置を独立管理する必要性を確認|
|クラス|`jpe:seismicMotion`|現在は観測・強震記録を直接生成|物理現象と観測結果を分離する場合に使用|
|関係|`jpe:isHypocenterOf`|`jpe:hasHypocenter`の逆プロパティ宣言のみで、明示トリプルは生成しない|推論で得るなら現状維持|
|関係|`jpe:detarminatedWith`、`jpe:estimatedWith`|震源決定に使った個々の波形が元データから復元されていない|pick/arrival対応時に再検討。綴り修正も必要|
|関係|`jpe:mainShock`、`jpe:afterShock`、`jpe:foreShock`|本震・余震・前震の分類処理がない|外部機関が明示する関係だけ登録する方針が安全|
|スナップショット|`jpe:DatasetSnapshot`、`snapshotOf`、`previousSnapshot`、`sourceChecksum`|通常変換ではスナップショット引数を指定していない|全件更新の本番処理で必須化を検討|
|SHACL|`jpe:DatasetSnapshotShape`|今回生成したデータにSnapshot個体がない|本番更新フローで検証する|
|互換語彙|`detarminatedWay`、`observedStaionNum`、`seismicIntensity`、`preShock`|旧TTLとの互換性のためdeprecatedで保持|新規生成には使わず、廃止時期を版方針で決める|

## 8. 現在使っているが独自オントロジーで十分に定義されていない項目

|項目|現状|問題|推奨|
|---|---|---|---|
|住所|`schema:address`とIMI語彙を直接利用|`jpe:`側には住所構造の定義がないが、外部語彙利用としては妥当|独自語彙を追加せず、SHACLだけ補強する|
|緯度・経度・標高|`schema:`を直接利用|座標参照系が明示されない|必要ならGeoSPARQLでWGS 84を明示|
|時刻|`xsd:dateTime`、JMA/J-SHISは`+09:00`、FDSNは入力オフセット|SHACLでタイムゾーン必須を完全には表現していない|タイムゾーン検査を追加|
|ラベル|`rdfs:label`、`skos:prefLabel`|使い分けがソースごとに不均一|ラベル生成規約を文書化|
|出典|`prov:wasDerivedFrom`|各レコードが同じ大容量ファイルURIを繰り返す|正規化より追跡性を優先するか、Distributionノード参照にするか検討|
|観測網|`jpe:observationNetwork`が`rdf:Property`|値が文字列で、K-NET/KiK-netをURIとして参照できない|ObservationNetworkクラスまたはSKOS概念化|

## 9. 推奨する確認順序

|順序|確認事項|判断が必要な理由|
|---:|---|---|
|1|PGA・PGV・SI・応答スペクトルの単位モデル|今後取り込むJ-SHIS列の意味を左右する|
|2|地震現象、震源解、マグニチュード解の分離|FDSNの複数解、J-SHISのJMA/NIED解を欠落なく扱う基礎になる|
|3|発震機構・断層面・モーメントテンソル|J-SHISとFDSNに共通する大きな未変換領域|
|4|観測点の地盤・機器・チャンネル|J-SHIS site列とFDSN StationXMLを共通化できる|
|5|歴史的不完全レコードの公開方針|必須項目を緩めると既存データ品質へ影響する|
|6|スナップショットを本番生成で必須にするか|バックアップ・全件更新方針をRDF上でも保証するため|

## 10. 現時点の結論

- 今回追加した語彙は、出典追跡、版管理、J-SHIS主要強震指標、住所構造化という当初の範囲には対応している。
- 気象庁・J-SHIS・FDSNの時刻はタイムゾーン付き`xsd:dateTime`で生成されている。
- J-SHIS原本のうち、応答スペクトル、地盤構造、発震機構・断層モデルは大部分が未変換である。
- FDSNはpreferred origin/magnitudeだけを採用しており、複数解・誤差・品質・波形到達情報は未変換である。
- `StrongMotionRecord`と`ObservedWaveShape`の不整合は解消済みであり、次の優先課題は強震指標の単位定義である。
- 未使用語彙を直ちに削除するより、地震現象と観測結果の将来モデルを決めた後に維持・非推奨を判断するのが安全である。
