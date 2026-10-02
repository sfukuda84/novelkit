---
name: "novelkit-all"
description: "章のアウトライン工程と執筆工程を通して実行する統括スキル。進捗の確認（途中の工程があれば続きから再開）、novelkit-chapter の本体（アウトライン・矛盾検出 ×3）、novelkit-write の本体（執筆・4 軸レビュー〈物語・整合・類似性・文章〉・収束と逆流・再レビュー）を続けて行い、章を完了にする。--auto を付けると、質問せずに推奨案を採用し、本文まで AI が書いて進める。作品の工程（novelkit-bootstrap）が済んでいなければ案内する。「この章を最後まで進めて」「全章を書いて」と言われたとき、または /novelkit-all と打たれたときに使う。"
argument-hint: "章の番号または範囲と、任意の --auto（例: 1, 02-04, all, all --auto, または省略して次の未完了）"
compatibility: "Requires git and Python 3.9+, novelkit project structure"
user-invocable: true
disable-model-invocation: false
---

# novelkit-all スキル（通し: C1 → C2〜C10 → C11）

アウトライン工程と執筆工程を、途中で止めずに通して実行する。本体の手順はこのファイルには書かず、次の 2 つのファイルの「§3 本体」をそのまま使う。

1. [`novelkit-chapter`](../novelkit-chapter/SKILL.md) の §3（C2〜C3-3）
2. [`novelkit-write`](../novelkit-write/SKILL.md) の §3（C4〜C10）

**ステップ番号、ヘルパースクリプト（`$NK`）、再開、モード、共通規則は [`novelkit-status`](../novelkit-status/SKILL.md) に従う。** 作業を始める前に必ず読むこと。

## 1. 引数

引数の解釈と複数の章の進め方は、[`novelkit-chapter`](../novelkit-chapter/SKILL.md) の §1 と同じである。自動検出では `$NK next --phase all` を使う。

## 2. 実行の流れ

対象の章ごとに、次を順に行う。

1. **作品の工程の確認**: `$NK state` で、W6（文体の決まり）・W8（章仕様）・W9（正典）が完了しているかを確かめる。未完了なら `novelkit-bootstrap` を案内する（自動モードでは `novelkit-bootstrap --auto` を先に実行する）。
2. **C1 準備**: `$NK state --chapter <章> --phase all` で `NEXT_STEP` を控え、再開の確認をする。続けて `$NK budget --step chapter` を実行し、STOP なら、この章に入らずに止まる（`novelkit-status` §3「セッションの区切り」）。途中の章を再開するときは、残りのステップの分だけを見積もってよい（C7 が残っていれば `--step C7`）。
3. **本体**: C2〜C10 のうち、`NEXT_STEP` 以降を順に実行する。各ステップの最後にチェックポイントを記録する。
4. **C11 章の完了**: `novelkit-status` §3「C11 章の完了」に従う。
5. 次の章があれば 2 に戻る。回数を数えられない環境（`budget` が UNMETERED）では、`session.chapters_unmetered` 章を終えたところで止まる。

通常モードでは、C4 の後に作者が下書きを推敲する時間を取る（`novelkit-write` §3）。作者が推敲のために止めた場合は、再実行で C5 から再開する。

## 3. 完了報告

`novelkit-chapter` と `novelkit-write` の完了報告の項目を、章ごとにまとめて報告する。範囲や `all` を指定したときは、最後に全体のまとめ（完了した章、止まった章とその理由、本文の合計字数、`$NK ai-usage` の結果）を付ける。
