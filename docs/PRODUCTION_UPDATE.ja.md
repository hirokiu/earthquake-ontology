# 公開サーバーでの地震LOD自動更新

## 推奨構成

本番環境ではQLeverをblue/greenの2スロットで起動し、nginxの`/sparql`を現在のスロットへ
プロキシします。更新中も現在のスロットは停止しません。非稼働側で新しいインデックスを構築し、
テストクエリがすべて成功した後にnginxのupstreamを原子的に差し替えます。

「稼働中ストアをクリアしてからロード」する方式は、ロード失敗時に空のエンドポイントが公開され、
数GBの再投入中に長時間停止するため採用しません。Dockerコンテナを毎回dropする必要もありません。
コンテナは実行環境、QLeverインデックスは交換対象として分けます。

## GRAPH設計

公開GRAPHは取得日時を含まない安定URIにします。

| 機関・データ | GRAPH URIの基底 |
| --- | --- |
| 気象庁月次震度 | `https://seismic.balog.jp/graph/jma/monthly-intensity` |
| 気象庁暫定震源 | `https://seismic.balog.jp/graph/jma/daily-hypocenters` |
| 気象庁観測点 | `https://seismic.balog.jp/graph/jma/intensity-stations` |
| USGS FDSN Event | `https://seismic.balog.jp/graph/usgs/fdsn-events` |
| EarthScope FDSN Station | `https://seismic.balog.jp/graph/earthscope/fdsn-stations` |
| J-SHISフラットファイル | `https://seismic.balog.jp/graph/nied/jshis-ground-motion-flatfile` |

変換時に`/hypocenters`、`/stations`、`/observed-waves`が付加されます。機関別の削除・再構築、
件数検査、由来確認が容易になり、異なる機関を横断するクエリではGRAPHを指定せずdefault unionを
利用できます。取得日時、原ファイルSHA-256、元URLはスナップショットマニフェストへ記録します。

## 初期導入

```bash
git clone https://github.com/hirokiu/earthquake-ontology.git
cd earthquake-ontology
git switch main
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
cp config/publication.example.yaml config/publication.yaml
```

QLeverの公式CLIを別途インストールし、`qlever --version`が実行できるようにします。標準設定では
QLever本体は公式Dockerイメージを利用し、blueを7011、greenを7012で起動します。

`config/publication.yaml`はサーバー固有設定です。秘密情報は書かず、認証情報は`EQ_`環境変数または
systemdの`EnvironmentFile`から渡します。

## nginx設定

nginxの`http`ブロック内にupstreamを用意します。`EQ_NGINX_UPSTREAM_LINK`が指すファイルには、
更新処理が現在のポートを1行で書き込みます。

```nginx
upstream earthquake_qlever {
    include /etc/nginx/conf.d/earthquake-qlever-current.conf;
}

location /sparql {
    proxy_pass http://earthquake_qlever/;
    proxy_set_header Host $host;
    proxy_read_timeout 180s;
}
```

初回は次の内容でincludeファイルを作成します。

```nginx
server 127.0.0.1:7011;
```

更新用ユーザーには、対象includeファイルの置換権限と、`systemctl reload nginx`だけをパスワードなしで
実行できる限定的なsudoers設定を与えます。Dockerソケットへの無制限アクセスはroot相当なので、
可能ならrootless Docker/PodmanまたはQLever公式のネイティブパッケージを利用します。

## 環境変数

```bash
export EQ_PUBLICATION_CONFIG=/path/to/earthquake-ontology/config/publication.yaml
export EQ_QLEVER_ROOT=/data/qlever/earthquake
export EQ_NGINX_UPSTREAM_LINK=/etc/nginx/conf.d/earthquake-qlever-current.conf
export EQ_QLEVER_BLUE_PORT=7011
export EQ_QLEVER_GREEN_PORT=7012
```

K-NET/KiK-netの認証取得を有効にする場合だけ、`EQ_NIED_USERNAME`と`EQ_NIED_PASSWORD`も安全な
EnvironmentFileから渡します。

## 手動テスト

最初に、ストアを変更しないdry-runを実行します。取得と差分判定は実行しますが、変換・QLever・nginx
切替コマンドは表示だけです。

```bash
scripts/update-production.sh --dry-run
```

初回全件構築、または差分がなくても再構築する場合は次を実行します。

```bash
scripts/update-production.sh --force
```

## cron

cronは同じ処理を重ねて起動しても、内部の排他ロックにより二重実行されません。ログローテーションは
OS側で設定してください。

```cron
17 3 * * * cd /path/to/earthquake-ontology && /usr/bin/env bash scripts/update-production.sh >> var/log/publication.log 2>&1
```

USGS FDSNのように過去年の応答へETag/Last-Modifiedがない取得元は、完全な差分確認に再ダウンロードが
必要です。日次設定は暫定・currentデータに限定し、全期間設定を週次または月次で実行する方法を推奨します。
ただし過去訂正を取り込む全件更新を廃止してはいけません。

## 実行フロー

1. 取得元一覧を再探索する。
2. ETag、Last-Modified、SHA-256で公開ファイルとローカル原本を比較する。
3. 差分がなければ終了する。
4. 差分があれば、取得済みの全現行原本から新しいN-Quadsスナップショットを作る。
5. 必須GRAPH、空ファイル、N-Quadsの基本構造を検査する。
6. 非稼働QLeverスロットの旧インデックスを停止し、新しい全件インデックスを作る。
7. 非稼働スロットを起動し、サンプル・論文デモの修正版クエリを実行する。
8. 成功時だけnginx upstreamを切り替え、公開URLでも同じテストを行う。
9. 直前スロットと原本、マニフェストをロールバック用に保持する。

取得・変換・検査・候補起動のいずれかが失敗した場合、active slotとnginxには触れません。

## ロールバック

直前スロットは次の更新まで停止・削除しません。切替後の公開URLテストが失敗した場合は、パイプラインが
自動的に直前スロットへ戻します。手動で戻す場合は直前スロットを指定して再度activateします。

```bash
scripts/qlever-blue-green.sh activate blue /unused
```

実際のactive slotは`var/publication/publication-state.json`で確認します。候補側のテストに失敗した場合は
切替自体を行わず、active slotをそのまま公開し続けます。

## Virtuosoを継続する場合

同じ取得・変換・検証までは利用できますが、数GBのデータをSPARQL `INSERT DATA`で送信する方式は避け、
Virtuoso Bulk Loaderで候補データベースまたは候補GRAPHへロードします。単一インスタンス内で
`CLEAR GRAPH`してから投入すると停止時間が生じるため、可能ならVirtuosoも別インスタンスまたは別DBを
用意し、nginxで切り替えます。

QLeverは全件再索引と大規模な読み取り中心の公開エンドポイントに適しているため、本データセットでは
QLever blue/greenを第一候補とします。頻繁なSPARQL UPDATEが必要になった場合だけVirtuoso継続を再検討します。
