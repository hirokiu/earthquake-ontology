# 地震オントロジーおよび地震 Linked Open Data (LOD) 🌍📊

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Journal](https://img.shields.io/badge/Journal-JSIK-blue.svg)](http://www.jsik.jp/)

本リポジトリは、情報知識学会誌（JSIK）への投稿論文 **「地震観測データの知識グラフ構築」** に関連するセマンティック・アーティファクト（オントロジーおよび Linked Open Data）を公開・提供するための公式アーカイブです。

## 📖 概要 (Overview)
日本をはじめとする地震多発地域では、気象庁（JMA）や防災科学技術研究所（NIED）、FDSNなど、多様な機関から膨大な観測データが公開されています。しかし、データフォーマットや構造的な意味（セマンティクス）が機関ごとに異なるため、分野を横断したデータ統合や柔軟な利活用が困難となっています。

こうした「データ統合の課題」を克服し、**意味的相互運用性（Semantic Interoperability）** を確立するために、以下のリソースを開発しました。

1. **地震オントロジー:** 地震の物理現象（断層のずれ）と観測現象（地表の揺れ）という多層的な構造を明確に分離・定義したドメインオントロジー。
2. **地震LOD:** 国内の気象庁（JMA）データと、国際デジタル地震観測網（FDSN）のデータを横断的に検索可能にした大規模な知識グラフ。

## 🔗 公開リソースとFAIR原則への対応
FAIR原則（Findable, Accessible, Interoperable, Reusable）に準拠し、本研究のリソースは以下のURLで公開および永続的にホスティングされています。

* **SPARQL エンドポイント:** [https://seismic.balog.jp/sparql/](https://seismic.balog.jp/sparql/)
* **オントロジー URI:** [https://seismic.balog.jp/ontology/](https://seismic.balog.jp/ontology/)
* **永続的アーカイブ:** 本GitHubリポジトリ（論文提出用ブランチ）は、オントロジーとサンプルデータセットの永続的なミラーとして機能します。

## 📦 データダウンロード (GitHub Releases)
完全なデータセットおよび安定版（Stable version）のファイルについては、本リポジトリの **[Releases](https://github.com/hirokiu/earthquake-ontology/releases)** セクションからダウンロード可能です。
* 地震LODの完全なRDFダンプ（Turtle形式）
* 地震オントロジーの最新定義ファイル

## 📂 リポジトリ構成
```text
.
├── ontology/
│   └── jp-earthquake.ttl       # 地震オントロジーの定義ファイル（Turtle形式）
├── datasets/
│   ├── JMA.zio                 # 気象庁 地震月報（カタログ編）からのLOD変換サンプル
│   └── FDSN.zip                # FDSN APIから生成されたLODサンプル
└── README.md
