---
name: "novelkit-chapter"
description: "章のアウトライン工程を実行する統括スキル。進捗の確認（既存の途中の工程があれば続きから再開）、1 話ごとのアウトライン（novelkit-outline でシーン台帳を作成）、矛盾検出 3 回（novelkit-analyze）を行う。speckit-feature に当たる。執筆とレビューは novelkit-write、通しは novelkit-all で行う。「この章のアウトラインを作って」「章の構成を固めて」と言われたとき、または /novelkit-chapter と打たれたときに使う。"
argument-hint: "章の番号または範囲と、任意の --auto（例: 1, 02-04, all, all --auto, または省略して次の未着手）"
compatibility: "Requires git and Python 3.9+, novelkit project structure"
user-invocable: true
disable-model-invocation: false
---

# novelkit-chapter スキル（章のアウトライン工程: C1 → C2〜C3-3）

章ごとに、シーン台帳の作成と 3 回の矛盾検出を行う。

- 執筆とレビュー（C4〜C11）は [`novelkit-write`](../novelkit-write/SKILL.md) が担当する。
- アウトラインから章の完了までを通して行う場合は [`novelkit-all`](../novelkit-all/SKILL.md) を使う。`novelkit-all` は、このファイルの「§3 本体」だけを実行する。

**ステップ番号、ヘルパースクリプト（`$NK`）、再開、モード、共通規則は [`novelkit-status`](../novelkit-status/SKILL.md) に従う。** 作業を始める前に必ず読むこと。

## 1. 引数

```text
$ARGUMENTS
```

| 指定 | 例 | 動作 |
|---|---|---|
| 単一 | `1`、`04`、`04-bow-and-partner` | `$NK resolve` で 1 章に決める |
| 範囲 | `02-04`、`2..4` | `$NK chapters` の結果から、番号が範囲内の章を番号順に選ぶ |
| 全件 | `all` | `$NK next --phase outline` を、空になるまで繰り返す |
| なし | （空） | `$NK next --phase outline` の 1 章。空なら対象なしと報告する |
| 自動モード | `--auto` | 上のいずれかと組み合わせる。質問せずに推奨案を採用して進める |

- 複数の章は、1 章ずつ直列に進める。前の章の終わりの状態が、次の章のアウトラインの前提になるためである。
- 前の章をまだ書いていない場合（`all` で全章のアウトラインを先に作る場合など）は、前の章のシーン台帳の最後の話を、終わりの状態の予定として前提にする（`novelkit-outline` §1）。書いた後に差が出たら、前の章の C9 が「上流からの変更」として届ける。
- `all` で途中の章が止まったら（自動モードの止まる場面）、`$NK next --phase outline --skip <止まった章>` で次に進む。

## 2. 実行の流れ（単独実行）

対象の章ごとに、次を順に行う。

1. **C1 準備**: `$NK state --chapter <章> --phase outline` を実行し、`NEXT_STEP` を控える。アウトライン工程は検索が少ないので、`budget` の確認は要らない（考証を足すために `novelkit-research-deep` を呼ぶときは、その前に `$NK budget --need <見積もり>` を実行する）。完了済みのステップがあれば、`novelkit-status` §3「開始時の確認」に従って再開する。`chapters/<章>/spec.md` がなければ、`novelkit-plot` を案内して止まる。
2. **本体**: §3 の C2〜C3-3 のうち、`NEXT_STEP` 以降を順に実行する。
3. 次の章があれば 1 に戻る。

## 3. 本体（C2〜C3-3）

| ステップ | 内容 | スキル |
|---|---|---|
| C2 | 1 話ごとのアウトライン（シーン台帳） | [`novelkit-outline`](../novelkit-outline/SKILL.md) |
| C3-1 | 矛盾検出 1 回目（重大・カバレッジ） | [`novelkit-analyze`](../novelkit-analyze/SKILL.md) `--round 1` |
| C3-2 | 矛盾検出 2 回目（詳細・整合） | `novelkit-analyze --round 2` |
| C3-3 | 矛盾検出 3 回目（最終確認） | `novelkit-analyze --round 3` |

各ステップの最後に、`$NK checkpoint <STEP> "<subject>" --chapter <章> --mode <auto|normal>` を記録する。

## 4. 完了報告

- 章ごとの話の数、山場、作者が書く話
- 矛盾検出 3 回の結果（直したもの、残した LOW）
- 飛ばした、または止まった章とその理由
- `--auto` のとき: `chapters/<章>/auto-decisions.md` の要約（見直しを勧める判断を先に）
- 次の案内: 執筆は `novelkit-write <章>`
