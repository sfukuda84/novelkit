---
name: "novelkit-bootstrap"
description: "新しい小説の立ち上げを通しで行う統括スキル。1 文のコンセプトから、種（novelkit-seed）→ 広域調査（novelkit-research-wide）→ 方向性の 3 案（novelkit-direction）→ 壁打ち（novelkit-sparring）→ 焦点調査（novelkit-research-deep）→ 文体の決まり（novelkit-constitution）→ プロット概要と核の設定（novelkit-synopsis）→ プロットの詳細化（novelkit-plot）→ 設定の整理（novelkit-canon）→ 全体の検証（novelkit-check）を順に実行し、章の工程に入れる状態にする。ステップごとにコミットし、中断しても続きから再開できる。--auto で質問せずに推奨案を採用して進め（本文も AI が書くモード）、--oneshot で最初に一度だけまとめて質問してから自動で進める。「小説を立ち上げて」「このコンセプトで小説を始めたい」と言われたとき、または /novelkit-bootstrap と打たれたときに使う。"
argument-hint: "[--auto | --oneshot] [1 文のコンセプト、または各ステップへの追加の希望]"
compatibility: "Requires git and Python 3.9+, WebSearch/WebFetch"
user-invocable: true
disable-model-invocation: false
---

# novelkit-bootstrap スキル（作品の立ち上げ: W0 → W10）

1 文のコンセプトから、章の工程（アウトライン・執筆・レビュー）に入れる状態までを、1 つの流れで作る。各ステップの中身は、それぞれのスキルの SKILL.md に従う。**このファイルには、順番と引き継ぎだけを書く。**

進捗の記録、モード、共通規則は [`novelkit-status`](../novelkit-status/SKILL.md) に従う。

## 1. 引数

```text
$ARGUMENTS
```

`--auto` と `--oneshot` は実行モードの指定であり、位置を問わない。取り除いた残りを、1 文のコンセプト（W1 の入力）か、各ステップへの追加の希望として扱う。

| 指定 | モード | 動作 |
|---|---|---|
| なし | 通常 | 各ステップのスキルの手順どおりに、作者に質問し、承認を得ながら進める。章の工程では AI が下書きを書き、作者が推敲する |
| `--auto` | 自動 | 作者に一度も質問せず、推奨案を採用して最後まで進める。章の工程でも AI が本文まで書く（`novelkit-status` §4） |
| `--oneshot` | 一括質問 | W0 で一度だけ、影響の大きい論点をまとめて質問する。以降は `--auto` と同じく自動で進める |

両方が指定されたときは `--oneshot` として扱う。

## 2. ステップ

| ステップ | 使うスキル | 完了の条件（成果物） |
|---|---|---|
| W0 | （このスキル） | Git リポジトリ、`.novelkit/config.yaml`、作品のディレクトリがある |
| W1 | [`novelkit-seed`](../novelkit-seed/SKILL.md) | `docs/concept/seed.md` |
| W2 | [`novelkit-research-wide`](../novelkit-research-wide/SKILL.md) | `docs/research/wide.md` |
| W3 | [`novelkit-direction`](../novelkit-direction/SKILL.md) | `docs/concept/direction.md`（選択あり） |
| W4 | [`novelkit-sparring`](../novelkit-sparring/SKILL.md) | `docs/concept/premises.md`（N1〜N12 が確定か対象外） |
| W5 | [`novelkit-research-deep`](../novelkit-research-deep/SKILL.md) | `docs/research/deep/`、`anachronism.md` |
| W6 | [`novelkit-constitution`](../novelkit-constitution/SKILL.md) | `.novelkit/memory/constitution.md` |
| W7 | [`novelkit-synopsis`](../novelkit-synopsis/SKILL.md) | `docs/plot/synopsis.md`、`structure.md`、核の設定（`canon/character/`、`rules.md`） |
| W8 | [`novelkit-plot`](../novelkit-plot/SKILL.md) | `chapters/<NN>-<slug>/spec.md`（全章）、`promises.md`、`threads.md` |
| W9 | [`novelkit-canon`](../novelkit-canon/SKILL.md) | `canon/` 一式 |
| W10 | [`novelkit-check`](../novelkit-check/SKILL.md) | `check.py` の ERROR が 0 件、`docs/check-report.md` |

各ステップの終わりに、`novelkit-status` §2 の subject でチェックポイントを記録する（`$NK checkpoint W<n> "<subject>" --mode <auto|normal>`）。一括質問モードでは `--mode auto` を渡す。

## 3. 再開

- 開始時に `$NK state` で完了済みのステップを調べ、最初の未完了のステップから再開する。
- 記録がなくても成果物がそろっているステップは、内容を確かめる。通常モードでは、完了として記録してよいかを作者に確かめる。自動モード・一括質問モードでは、確かめずに記録する。
- 再開する場合は、完了済みのステップと再開するステップを示してから進める。

## 4. 手順

### W0: 事前確認と初期化

1. Git リポジトリでなければ、`git init` してよいかを確かめてから初期化する（自動モードでは初期化する）。未コミットの変更があれば、状況を示して対応を確かめる（自動モードでは止まる）。
2. `$NK init --title <仮題>` で `.novelkit/config.yaml` と作品のディレクトリを作る。既存のファイルは変えない。
3. 引数にコンセプトがあれば、W1 の入力として控える。なく、`seed.md` もなければ、W1 で聞く（自動モードでは止まる）。
4. `--oneshot` のときは、§7 の一括質問を行う。
5. 変更があれば、初回のコミットを作る（trailer なし。`chore(novel): novelkit を初期化`）。`new_project.py` で作った作品では、初回のコミットは済んでいるので、変更がなければ作らない。

### W1〜W10

各スキルの手順を最後まで行う。ヒアリング、調査、案の比較、承認、検証を省かない。

**W2 と W5 の前に**、`$NK budget --step W2`（W5 は `--step W5`）を実行する。STOP なら、その工程に入らずに止まり、新しいセッションでの再開を案内する（`novelkit-status` §3「セッションの区切り」）。

引き継ぎの注意:

- **W2 → W3**: 重なりが大きい類似作品を、W3 の「類似作品との差」で必ず扱う。
- **W3 → W4**: 選ばなかった案は `backlog.md` に残る。W4 の壁打ちで、要素を拾い直してよい。
- **W4 → W5**: 方向性が大きく変わったら（ジャンル、主人公）、W2 に戻って再調査する。通常モードでは戻るかを確かめる。自動モードでは戻らず、`auto-decisions.md` に記録する。
- **W5 → W6**: 考証の要らない題材では、W5 は短くてよい。ただし `anachronism.md`（異世界なら「この世界にないもの」）は必ず作る。
- **W4 → W6**: W6（文体の決まり）は W5（考証）の結果にほとんど依存しないので、W5 をサブエージェントに任せている間に W6 を書いてよい。その場合は、`checkpoint --paths` で W5 と W6 の成果物を分けてコミットする（`novelkit-status` §3）。
- **W4・W7 → config**: 仮題を決めたり変えたりしたら、`.novelkit/config.yaml` の `title` も更新する。
- **W6 → W7**: 声のサンプルが暫定なら、章の工程の最初の話を作者が推敲した後に差し替えるよう、完了報告に書く。
- **W8 → W9**: 章仕様の IR で「伏せる」とした名前・用語は、W9 で正典の `reveal_from` の対象にする。
- **W9 → W10**: W10 で ERROR が出たら、該当するスキルに戻って直す。

### W10 の後

`config.yaml` の `session.stop_after_work` が true（既定）なら、章の工程には進まずに止まる。完了報告の「次の案内」の先頭に、「**新しいセッションを開いて** `novelkit-all` を実行する」と書く。自動モードでも止まる。

## 5. 短編の場合

章が 1 つで、話が 5 本以下の短編（`premises.md` の N9）では、次のように簡略にしてよい。

- **W8**: 章の分割案の提示と承認を省く（章は 1 つ）。章仕様が作品全体の仕様を兼ねる。
- **W7〜W8 の伏線台帳・筋の台帳**: 章の単位で書いても全部「第1章」になり意味がないので、W8 では空けておき、C2（アウトライン）で話番号から書く。
- **C3**: `novelkit-analyze` の短編の扱い（1 回目と 2 回目をまとめてよい）に従う。
- 省いた手順は、完了報告に書く。

## 6. 完了報告

- 作成したファイルの一覧
- ログラインと仮題、選んだ方向性（ジャンル、中心の考え、読後感）
- N1〜N12 の要約
- 構成の型と、章の一覧
- 主要人物と、伏せる名前
- 検証の結果
- 自動モード・一括質問モードのとき: `docs/auto-decisions.md` のうち、見直しの優先度が「高」の判断の一覧と、見直しに使うスキル
- 次の案内:
  - **新しいセッションを開いて**、`novelkit-all`（引数なし）で、最初の章からアウトライン・執筆・レビューを通して進める。`novelkit-all all --auto` で全章を無人で進めることもできる（検索の残りが足りなくなると、章の区切りで止まる。そのときは、また新しいセッションで同じコマンドを実行する）
  - 工程を分けたいときは、`novelkit-chapter`（アウトラインと矛盾検出）と `novelkit-write`（執筆とレビュー）を使う

## 7. 一括質問（`--oneshot` の W0）

次の候補のうち、引数と既存の成果物から決まらないものを上から順に最大 4 つ選び、AskUserQuestion の 1 回にまとめて質問する。各問には、推奨案を先頭に `(Recommended)` 付きで置く。

| 順 | 論点 | 使うステップ |
|---|---|---|
| 1 | 発表先と想定読者（N2） | W3、W4、W6 |
| 2 | ジャンルの希望と、避けたいもの（N3、N11） | W3、W4 |
| 3 | 分量（短編／長編／長期連載）（N9） | W4、W7、W8 |
| 4 | 結末の手触り（ハッピー／ビター／悲劇）（N7） | W3、W7 |
| 5 | 視点と人称（N8） | W6 |
| 6 | 実在の人物・事件をモデルにするか | W2、W5 |

- 回答は `docs/concept/seed.md` の末尾に「追記（YYYY-MM-DD、一括質問の回答）」の節として書く。以降のスキルは、この回答を「確定」の根拠として使える。
- 再開したときに、この節がすでにあれば質問しない。
- 質問はこの 1 回だけにする。以降は自動モードで決める。

## 8. 規則

- 各ステップの中身は、それぞれのスキルの SKILL.md に従う。このスキルで手順を省かない。自動モード・一括質問モードでは、ヒアリングや承認の手順を `novelkit-status` §4 の規則で置き換える（調査、比較、書き出し、検証は省かない）。
- 作者が「このステップは後でやる」と明示した場合は、飛ばして次に進んでよい。飛ばしたステップは記録せず（再実行時に再開の対象になる）、完了報告に影響を書く。
