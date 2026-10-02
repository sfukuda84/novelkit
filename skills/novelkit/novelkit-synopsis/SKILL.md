---
name: "novelkit-synopsis"
description: "確定した前提（docs/concept/premises.md）から、プロット概要と核の設定を同時に作るスキル。スノーフレーク法で 1 文 → 5 文（導入・災難 1〜3・結末）→ 1 ページのあらすじへ広げ、構成の型（三幕構成・Save the Cat・7 ポイント・起承転結・序破急・ヒーローズ・ジャーニー）にビートを配置して docs/plot/synopsis.md と docs/plot/structure.md に書く。同時に、主要人物の核（Ghost・Lie・Want・Need・Truth）と世界の規則の核を canon/ に作り、読者への約束の一覧を始める。novelkit-bootstrap の W7。「プロット概要を作って」「あらすじを作って」と言われたとき、または /novelkit-synopsis と打たれたときに使う。"
argument-hint: "[構成の型（例: 三幕、savethecat、7point、kishotenketsu、johakyu、herojourney）] [--auto]"
compatibility: "Uses docs/concept/premises.md, docs/research/, .novelkit/memory/constitution.md"
user-invocable: true
disable-model-invocation: false
---

# novelkit-synopsis スキル（W7: プロット概要＋核の設定）

プロットは、人物の欲しいものと欠けているものから生まれる。そのため、**プロット概要と、主要人物・世界の核を同じ工程で作り、互いに合わせる**。年表・用語・関係図などの詳しい設定は、プロットの詳細化（W8）の後の設定の整理（W9）で作る。

進捗の記録、モード、質問の規則は [`novelkit-status`](../novelkit-status/SKILL.md) に従う。

## 1. 入力

- `docs/concept/premises.md`（N1〜N12。とくに N1、N3〜N7、N9、N10）
- `docs/concept/direction.md`、`docs/research/`（wide.md、deep/、anachronism.md）
- `.novelkit/memory/constitution.md`
- 引数の構成の型（なければ N9 の型）

`premises.md` に未決の必須項目があれば、`novelkit-sparring` を案内する。作者が後で決めると明示した項目は、`[NEEDS CLARIFICATION]` のまま進めてよい。

## 2. 手順

### ステップ 1: 1 文と 5 文

1. N1 のログラインを、物語の 1 文要約にする（主人公・目的・障害・結末の方向）。
2. 5 文の段落要約を書く。**導入 / 災難 1 / 災難 2 / 災難 3 / 結末** の 5 文である。災難は、主人公の計画が崩れて状況が悪化する出来事で、後のものほど大きくする。災難 3 の後に、主人公が Lie を捨てて Truth を選ぶ転換を置く（N5）。

### ステップ 2: 核の設定

5 文を支える人物と世界の核を作る。

- **主要人物**: 主人公、敵対者、主要な協力者（3〜6 人）。`canon/character/<名前>.md` を [../novelkit-canon/templates/character.md](../novelkit-canon/templates/character.md) の様式で作り、このステップでは次の欄だけを埋める。残りの欄は W9 で埋める。
  - 名前（仮でよい）、役割
  - Ghost・Lie・Want・Need・Truth（主人公以外も、物語での変化がある人物は書く）
  - 物語での変化（始まりの状態 → 終わりの状態。変わらない人物は「不変」と書き、理由を添える）
  - 敵対者は「言い分」（読者が半分うなずける理屈）
  - フロントマターの `type: character`、`ai: always`（主要人物）
- **世界の規則**: N10 から、物語が成り立つのに必要な規則だけを `canon/rules.md` に書く。**様式は [../novelkit-canon/templates/rules.md](../novelkit-canon/templates/rules.md) をコピーして使う**（「変更の記録」の節は、後の逆流で使うので消さない）。各規則に「物語での働き」（どの場面の制約・代償になるか）を添える。働きのない規則は書かない。
- 人物と 5 文を照らし合わせる。主人公の Want が導入と災難を動かし、Need が結末の選択を決めているか。敵対者の言い分が、災難のどれかを生んでいるか。合っていなければ、5 文か人物を直す。

### ステップ 3: 1 ページのあらすじ

5 文の各文を 1 段落に広げ、1 ページ（2,000〜3,000 字）のあらすじにする。結末まで書く。ぼかさない。

### ステップ 4: 構成の型とビート

構成の型を選び、ビートを配置して `docs/plot/structure.md` に書く。

| 型 | 向いているもの | ビートの例 |
|---|---|---|
| 三幕構成（既定） | ほとんどの長編 | 第 1 幕（〜25%）、プロットポイント 1、ミッドポイント（50%）、プロットポイント 2（〜75%）、クライマックス、解決 |
| Save the Cat（15 ビート） | 商業的な長編、映像的な話 | オープニング・イメージ（1%）、テーマの提示（5%）、きっかけ（10%）、第 2 幕へ（25%）、B ストーリー（22%）、ミッドポイント（50%）、すべてを失って（75%）、第 3 幕へ（80%）、ファイナル・イメージ（99〜100%）など |
| 7 ポイント | 結末から逆算したいとき | フック、ターン 1、ピンチ 1、ミッドポイント、ピンチ 2、ターン 2、解決（フックと解決は逆の状態） |
| 起承転結 | 短編、1 章・1 話の単位 | 起、承、転、結 |
| 序破急 | 短い尺、見せ場を早く出したいとき | 序、破、急 |
| ヒーローズ・ジャーニー | 冒険・成長の話 | 日常世界 → 冒険への誘い → … → 宝を持っての帰還（12 段階） |

- 各ビートに、あらすじのどの出来事が当たるかと、全体のどの位置（% と、N9 の章の数から見た章番号）に置くかを書く。
- 長期連載（N9 で章の数が多い）では、作品全体の型と別に、**章ごとの型**（例: 各章を起承転結）を決めてよい。
- **目的の層**: 表層（目に見える目的）・中層（人物の関係の目的）・深層（Need）に分け、それぞれどの章で決着するかを書く。

### ステップ 5: 約束の一覧

冒頭で読者にする約束（何が起きそうか、何が明かされそうか、どんな感情が得られそうか）を 3〜7 個挙げ、`docs/plot/promises.md`（様式: [../novelkit-plot/templates/promises.md](../novelkit-plot/templates/promises.md)）を作る。この時点では「張る」と「回収予定」を大まかな位置（例: `序盤`、`第3章`）で書く。W8 では章の単位（`第3章`）にそろえ、C2（アウトライン）で話番号にする。種類は `約束` とする。

### ステップ 6: 提示と承認

1 文、5 文、主要人物の核、構成の型とビート、約束の一覧をまとめて示す。

- **通常モード**: 次を推奨案つきで確かめる。
  - 5 文（とくに災難 3 と結末）
  - 主人公の Lie と Truth
  - 構成の型

  修正があれば直して再提示する。1 ページのあらすじは、承認の後に仕上げてよい。
- **自動モード**: 推奨案のまま書き出す。結末、主人公の Lie と Truth、主要人物の生死は、`docs/auto-decisions.md` に見直しの優先度「高」で記録する。

## 3. 出力

- `docs/plot/synopsis.md`（様式: [templates/synopsis.md](./templates/synopsis.md)）
- `docs/plot/structure.md`（様式: [templates/structure.md](./templates/structure.md)）
- `canon/character/<名前>.md`（核の欄だけ）、`canon/rules.md`（核の規則だけ）
- `docs/plot/promises.md`（約束の一覧）

終わったら `W7` のチェックポイントを記録する。

## 4. 完了報告

- 1 文と 5 文
- 主要人物と、それぞれの Want・Need・変化
- 構成の型と、主なビートの位置
- 約束の一覧
- 次の案内: `novelkit-plot`（W8）
