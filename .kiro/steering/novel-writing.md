---
inclusion: always
---

# 小説執筆ルール（novelkit）

このプロジェクトは novelkit で小説を書く。本文は、企画 → 前提 → プロット → 章仕様 → シーン台帳の順に作った設計から書き、設計を経ずに本文を書かない。

## 基本原則

1. **設計が先、本文が後**: 新しい章や話は、`chapters/<章>/spec.md` → `scenes.md` を作ってから書く。
2. **文体の決まりが最上位**: `.novelkit/memory/constitution.md` をすべての判断の基準とする。シーン台帳や本文が文体の決まりと矛盾する場合は、先に文体の決まりとの整合を取る。
3. **正典は 1 か所**: 人物・場所・年表・用語などの事実は `canon/` にだけ書く。食い違ったら、文体の決まりの「正典の優先順位」に従う。
4. **推測で埋めない**: 作者が決めていないことは `[NEEDS CLARIFICATION: ...]` として明示し、質問で解消する。自動モード（`--auto`）では、推奨案を明示して採用し、`auto-decisions.md` に記録することで確認に代える（`novelkit-status` §4）。
5. **本文と設計を同期させる**: 書いている途中で設計の誤りや、より良い展開が見つかったら、本文だけを直さず、`novelkit-converge` で台帳・章仕様・正典にも反映する。
6. **作者の本文を守る**: 作者が確定させた本文（`status: 確定`）と、作者が書く話（`[人]`）を、AI の判断だけで書き換えない。
7. **盗作をしない**: 章ごとに類似性軸（`novelkit-review originality`）で、本文の特徴的な文と展開を Web で検索し、既存作品との表現の一致と、特徴的な展開の組み合わせの一致を確かめる。AI の判定は一次のふるい分けであり、疑わしいものは作者か専門家に確かめる。
8. **出典を残す**: 調査の事実には、出典 URL と参照日を付ける。AI が挙げた作品名・史実は、実在を確かめてから使う。

## 工程

### 作品の工程（`novelkit-bootstrap` が W1〜W10 を通しで行う）

| ステップ | スキル | 成果物 |
|---|---|---|
| W1 | `novelkit-seed` | `docs/concept/seed.md`（1 文 → ログライン） |
| W2 | `novelkit-research-wide` | `docs/research/wide.md`（類似作品・実例・歴史・トロープ） |
| W3 | `novelkit-direction` | `docs/concept/direction.md`（方向性の 3 案と選択） |
| W4 | `novelkit-sparring` | `docs/concept/premises.md`（N1〜N12）、`backlog.md` |
| W5 | `novelkit-research-deep` | `docs/research/deep/`、`anachronism.md` |
| W6 | `novelkit-constitution` | `.novelkit/memory/constitution.md` |
| W7 | `novelkit-synopsis` | `docs/plot/synopsis.md`、`structure.md`、核の設定 |
| W8 | `novelkit-plot` | `chapters/<NN>-<slug>/spec.md`、`promises.md`、`threads.md` |
| W9 | `novelkit-canon` | `canon/` 一式 |
| W10 | `novelkit-check` | 機械検証 |

### 章の工程（`novelkit-chapter`・`novelkit-write`・`novelkit-all`）

| ステップ | スキル | 成果物 |
|---|---|---|
| C2 | `novelkit-outline` | `chapters/<章>/scenes.md`（シーン台帳） |
| C3-1〜3 | `novelkit-analyze` | `chapters/<章>/reviews/analyze-*.md` |
| C4 | `novelkit-draft` | `draft/<NN>/*.md`、`state.md`、`summaries.md` |
| C5〜C8 | `novelkit-review`（story → consistency → originality → prose） | `chapters/<章>/reviews/*.md` |
| C9 | `novelkit-converge` | 収束タスク、正典・台帳の更新 |
| C10 | `novelkit-review`（recheck） | 再レビュー |
| C11 | `novelkit-status finish` | 引き継ぎ書 |

公開・応募の準備は `novelkit-publish` で行う。進捗の確認・再開・文脈パック・引き継ぎ書は `novelkit-status` で行う。

## モード

| | 通常モード（既定） | 自動モード（`--auto`） |
|---|---|---|
| 本文 | AI が下書きし、作者が推敲して確定する | AI が本文まで書いて確定する |
| 質問 | 推奨案を添えて質問し、合意を得てから進める | 質問せず推奨案を採用し、`auto-decisions.md` に記録する |

## セッションの区切り

Web 検索には 1 セッションあたりの回数の上限がある。作品の工程（W10）の後は必ずセッションを区切り、W2・W5・C7 の前と章に入る前には `novelkit.py budget` で残りを確かめ、STOP なら工程の区切りで止まる（`novelkit-status` §3「セッションの区切り」）。止まるのは失敗ではない。新しいセッションで同じスキルを実行すれば、続きから再開する。

## エージェントの行動規範

- 作者が新しい話を書いてほしいと頼み、その章の `scenes.md` がまだなければ、いきなり書かず、`novelkit-outline` から始めることを提案する。
- 各スキルは、前の工程の成果物を前提にする。前提の成果物がなければ、欠けている工程を案内する。
- 1 つの工程が終わったら結果を要約し、次に実行すべきスキルを示す。
- 誤字の修正など、設計を変えない軽微な修正は、工程を省いてよい。判断に迷ったら作者に確かめる。
- スクリプトは Python（3.9 以上）で書かれており、`python3 <スクリプト>` の形で呼ぶ。`python3` がない環境では `python` または `py -3` に読み替える。
- スキルの本文にある `AskUserQuestion`（選択肢付きの質問）、`WebSearch` / `WebFetch`（Web 検索とページの取得）、Agent（サブエージェント）は Claude Code のツール名である。ほかのエージェントでは同じ働きのツールを使う。

## ディレクトリ構成

```text
.novelkit/
├── config.yaml              # パスの対応、1 話の字数、文章の検査のしきい値、文脈パックの設定
└── memory/constitution.md   # 文体の決まり（最上位の規範）
docs/
├── auto-decisions.md        # 自動モードで決めたこと（作品の工程）。章の工程の分は chapters/<章>/auto-decisions.md
├── concept/                 # seed.md、direction.md、premises.md、backlog.md（ネタ帳）
├── research/                # wide.md、deep/、anachronism.md
└── plot/                    # synopsis.md、structure.md、promises.md、threads.md
canon/                       # 正典（character/、place/、org/、item/、rules.md、glossary.md、timeline.md、relations.md）
chapters/<NN>-<slug>/        # spec.md、scenes.md、state.md、summaries.md、reviews/、context/（生成物）
draft/<NN>/                  # 本文
publish/                     # 公開・応募の準備
handover/                    # 引き継ぎ書
```

パスは `.novelkit/config.yaml` で変えられる。既存作品では、ファイルを動かさずにパスを合わせてよい。
