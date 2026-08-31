# 気象庁命名地震活動

気象庁の命名地震は個別震源ではなく `jpe:NamedEarthquakeActivity` として表す。これは
`schema:EventSeries` の下位にある実世界の一連の地震活動である。取得原本、HTTPメタデータ、
SHA-256を保存し、厳格な表構造検査後にRDFを生成する。

所属候補は `jpe:EarthquakeActivityMembership` として根拠・状態・方式・信頼度を保持する。
自動処理は `Candidate` のみを作り、包含トリプルを作らない。公式列挙または人手確認で
`Confirmed` へ昇格した場合だけ `jpe:hasMemberEarthquake`、`schema:subEvent` と逆関係を生成する。
JMA/J-SHISの震源解同士には `owl:sameAs` を用いない。

災害名称は `jpe:DisasterCase` の別リソースにし、`jpe:causedDisaster` で活動へ関連付ける。
能登半島地震の開始は公式記載どおり2020年12月であり、2024年1月1日の単一震源に縮退させない。

再現手順:

```bash
earthquake-named-earthquakes fetch raw.html --metadata raw.metadata.json
earthquake-named-earthquakes convert raw.html named.ttl --json named.json --diff diff.json \
  --graph-uri https://seismic.balog.jp/graph/jma/named-earthquakes/20260831 \
  --update insert-named-earthquakes.ru
earthquake-named-earthquakes candidates raw.html jma-catalog.ttl memberships.ttl \
  --catalog-version VERSION --generated-at 2026-08-31T00:00:00Z
python -m unittest discover -s tests -v
```
