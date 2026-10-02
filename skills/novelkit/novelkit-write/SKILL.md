---
name: "novelkit-write"
description: "章の執筆工程を実行する統括スキル。進捗の確認（途中の工程があれば続きから再開）、執筆（novelkit-draft。通常モードは AI の下書き、--auto は AI が本文まで書く）、4 軸レビューと修正（novelkit-review の物語軸 → 整合軸 → 類似性軸 → 文章軸）、収束と逆流（novelkit-converge）、再レビュー（novelkit-review recheck）、章の完了（引き継ぎ書の生成）までを行う。speckit-coding に当たる。シーン台帳（scenes.md）が必要で、なければ novelkit-chapter を案内する。「この章を書いて」「執筆からレビューまで進めて」と言われたとき、または /novelkit-write と打たれたときに使う。"
argument-hint: "章の番号または範囲と、任意の --auto（例: 1, 02-04, all, all --auto, または省略して次の未執筆）"
compatibility: "Requires git and Python 3.9+, novelkit project structure"
user-invocable: true
disable-model-invocation: false
---

# novelkit-write スキル（章の執筆工程: C1 → C4〜C10 → C11）

アウトライン工程（[`novelkit-chapter`](../novelkit-chapter/SKILL.md)）で作ったシーン台帳に基づき、執筆、4 軸レビュー、収束と逆流、再レビューを行い、章を完了にする。

- アウトラインから章の完了までを通して行う場合は [`novelkit-all`](../novelkit-all/SKILL.md) を使う。`novelkit-all` は、このファイルの「§3 本体」だけを実行する。

**ステップ番号、ヘルパースクリプト（`$NK`）、再開、モード、共通規則は [`novelkit-status`](../novelkit-status/SKILL.md) に従う。** 作業を始める前に必ず読むこと。

## 1. 引数

引数の解釈と複数の章の進め方は、[`novelkit-chapter`](../novelkit-chapter/SKILL.md) の §1 と同じである。自動検出では `$NK next --phase write` を使う。

- `BLOCKED: アウトライン工程（…）が未完了` と出たら、その章の `novelkit-chapter` を案内する。自動モードでは `novelkit-chapter <章> --auto` を先に実行してから進める。

## 2. 実行の流れ（単独実行）

対象の章ごとに、次を順に行う。

1. **C1 準備**: `$NK state --chapter <章> --phase write` を実行し、`NEXT_STEP` を控える。`NEXT_STEP: BLOCKED`（アウトライン工程が未完了）か、`chapters/<章>/scenes.md` がなければ、`novelkit-chapter` を案内して止まる（自動モードでは `novelkit-chapter <章> --auto` を先に実行する）。
2. **本体**: §3 の C4〜C10 のうち、`NEXT_STEP` 以降を順に実行する。
3. **C11 章の完了**: `novelkit-status` §3「C11 章の完了」に従う。
4. 次の章があれば 1 に戻る。

## 3. 本体（C4〜C10）

| ステップ | 内容 | スキル |
|---|---|---|
| C4 | 執筆（1 話ずつ。状態・要約・伏線台帳の更新を含む） | [`novelkit-draft`](../novelkit-draft/SKILL.md) |
| C5 | レビュー・物語軸（ストーリー性）と修正 | [`novelkit-review`](../novelkit-review/SKILL.md) `story` |
| C6 | レビュー・整合軸（方向性・全体プロット・正典）と修正 | `novelkit-review consistency` |
| C7 | レビュー・類似性軸（類似作品を検索し、盗作に当たらないかを確かめる）と修正 | `novelkit-review originality` |
| C8 | レビュー・文章軸（誤字脱字・表現・論理構成）と修正 | `novelkit-review prose` |
| C9 | 収束と逆流 | [`novelkit-converge`](../novelkit-converge/SKILL.md) |
| C10 | 再レビュー（修正の副作用） | `novelkit-review recheck` |

- **C7 の前に** `$NK budget --step C7` を実行する。STOP なら C7 に入らずに止まり、新しいセッションでの再開を案内する（C6 までのチェックポイントは記録済み）。
- 複数の章を続けて進めるときは、次の章の C1 で `$NK budget --step chapter` を実行する。UNMETERED なら `session.chapters_unmetered` 章で止まる。
- C5 → C6 → C7 → C8 の順を守る。上の軸の CRITICAL・HIGH が 0 件になってから、下の軸に進む。
- 各ステップの最後に、`$NK checkpoint <STEP> "<subject>" --chapter <章> --mode <auto|normal>` を記録する。
- 通常モードでは、C4 の後に、作者が下書きを推敲する時間を取る。作者が「推敲してから進める」と言えば、そこで止まる。再実行すると C5 から再開する。作者が推敲した本文は `status: 確定` にする。

## 4. 完了報告

- 書いた話の数・字数と、`status`（下書き / 確定）の内訳
- 作者が書く話で、残っているもの
- 4 軸レビューで見つかって直した指摘（軸・重大度別）
- 類似性軸: 検索した範囲、見つかった類似作品と判定。CRITICAL・HIGH があれば、作者か専門家に確かめるよう書く
- 収束と逆流の内訳と、後続の章への影響
- `check.py` の結果
- `--auto` のとき: `chapters/<章>/auto-decisions.md` の要約（見直しを勧める判断を先に）
- 次の案内: `$NK next --phase write` の結果。公開の準備は `novelkit-publish`
