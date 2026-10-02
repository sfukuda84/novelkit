# novelkit

AI と一緒に小説を書くためのスキルセット。[my-speckit-scaffold](../speckit/README.md)（仕様駆動開発）の作りを小説に移したもので、1 文のコンセプトから、調査・方向性・壁打ち・プロット・設定・1 話ごとのアウトライン・執筆・4 軸レビュー（物語・整合・類似性〈盗作の確認〉・文章）までを、工程ごとのスキルと、それをつなぐ統括スキルで進める。

- Claude Code、Codex CLI、Antigravity、Kiro CLI、opencode で同じスキルと規則を使う（規則の正本は `.kiro/steering/`、スキルの本体は `skills/novelkit/`）。
- ステップが終わるたびにコミットし、trailer（`Novelkit-Step`、`Novelkit-Chapter`）から進捗を判定する。中断しても続きから再開できる。
- スクリプトは Python（標準ライブラリのみ、3.9 以上）で、macOS、Linux、Windows で動く。

## 工程

```text
作品の工程（novelkit-bootstrap）
 W1 種 → W2 広域調査 → W3 方向性の 3 案 → W4 壁打ち → W5 焦点調査 → W6 文体の決まり
 → W7 プロット概要＋核の設定 → W8 プロットの詳細化（章仕様） → W9 設定の整理（正典） → W10 検証

章の工程（novelkit-chapter → novelkit-write、通しは novelkit-all）
 C2 1 話ごとのアウトライン（シーン台帳） → C3 矛盾検出 ×3
 → C4 執筆 → C5 物語軸 → C6 整合軸 → C7 類似性軸 → C8 文章軸 → C9 収束と逆流 → C10 再レビュー → C11 完了
```

| 区分 | スキル | 工程 | speckit の元 |
|---|---|---|---|
| 統括 | `novelkit-bootstrap` | W0〜W10（`--auto`、`--oneshot`、`--adopt`） | speckit-bootstrap |
| 統括 | `novelkit-chapter` | C2〜C3-3 | speckit-feature |
| 統括 | `novelkit-write` | C4〜C11 | speckit-coding |
| 統括 | `novelkit-all` | C2〜C11 | speckit-all |
| 共通 | `novelkit-status` | 進捗・再開・モード・文脈パック・引き継ぎ書 | speckit-worktree |
| 企画 | `novelkit-seed` | W1 | — |
| 企画 | `novelkit-research-wide` | W2 | concept-2-feature の競合調査 |
| 企画 | `novelkit-direction` | W3 | speckit-architecture（3 案の比較） |
| 企画 | `novelkit-sparring` | W4 | concept-2-feature のヒアリング |
| 企画 | `novelkit-research-deep` | W5 | — |
| 設計 | `novelkit-constitution` | W6 | speckit-constitution |
| 設計 | `novelkit-synopsis` | W7 | — |
| 設計 | `novelkit-plot` | W8 | speckit-specify ＋ clarify ×2 |
| 設計 | `novelkit-canon` | W9 | speckit-common-feature |
| 設計 | `novelkit-check` | W10 ほか | validate.py |
| 章 | `novelkit-outline` | C2 | speckit-tasks |
| 章 | `novelkit-analyze` | C3-1〜3 | speckit-analyze |
| 章 | `novelkit-draft` | C4 | speckit-implement |
| 章 | `novelkit-review` | C5〜C8（物語・整合・類似性・文章）、C10 | speckit-review |
| 章 | `novelkit-converge` | C9 | speckit-converge |
| 公開 | `novelkit-publish` | 任意 | speckit-presentation |

## モード

| | 通常モード（既定） | 自動モード（`--auto`） |
|---|---|---|
| 本文 | AI が下書きし、作者が推敲して確定する（`status: 下書き` → `確定`） | AI が本文まで書いて確定する |
| 質問 | 推奨案を添えて質問し、合意を得てから進める | 質問せず推奨案を採用し、`auto-decisions.md` に記録する |
| 作者が書く話 | シーン台帳で `[人]` を付けた話は作者が書く | 使わない |

`novelkit-bootstrap` には、最初に一度だけ質問して以降を自動で進める `--oneshot` もある。

## セッションの区切り

Web 検索には 1 セッションあたりの回数の上限がある（Claude Code で観測した値は 200 件）。調査（W2・W5）と類似性軸（C7）は検索が多いので、novelkit はセッションを工程の境目で区切る。

- **必ず区切る**: 作品の工程（W10）の後。新しいセッションで `novelkit-all` を始める。
- **回数を数えて区切る**: 作品を作るときに `.claude/settings.json` にフックが入り、セッションごとの Web 検索の回数を `.novelkit/usage/` に記録する。W2・W5・C7 の前と、章に入る前に `novelkit.py budget` で残りを確かめ、足りなければ工程の区切りで止まる。新しいセッションで同じコマンドを実行すれば、続きから再開する。
- **数えられない環境**（Claude Code 以外）では、1 セッション 1 章で止まる。
- 上限と見積もりは `.novelkit/config.yaml` の `session` で変える。既存の作品には `python3 skills/novelkit/novelkit-status/scripts/novelkit.py hooks install` でフックを入れる。

## コマンドの導入と更新

[speckit](https://github.com/sfukuda84/my-speckit-scaffold) の `new-speckit-project` と同じく、uv のツールとして入れる。

```bash
uv tool install "git+https://github.com/sfukuda84/novelkit#subdirectory=tool"   # 導入（初回だけ）
uv tool upgrade new-novelkit-project                                                     # コマンドの更新
new-novelkit-project update [作品のディレクトリ]                                   # 作成済みの作品に scaffold の新しい版を取り込む
```

- `new-novelkit-project` は、実行のたびに scaffold を GitHub から取得して作品を作る（`--ref` でブランチやタグ、`--repo` でリポジトリを指定できる）。
- `update` は、scaffold の持ち物（スキル、ルールなど）だけを取り込み、1 つのコミットにする。scaffold のどの版とも中身が一致しないファイルは手で直したものとみなして上書きせず、新しい版を `.scaffold-new/` に置く。取り込みで残した同名のスキルにも触らない。`--dry-run` で、何が変わるかだけを見られる。
- スキルを scaffold へのリンクで置いた作品（`--link`）は、スキルがすでに最新なので、`update` はリンクの外（ルールなど）だけを更新する。
- 手元の scaffold（このリポジトリの clone）から使うときは、`scripts/new-novelkit-project` を直接実行するか、`--scaffold <ディレクトリ>` を付ける。`--link` は手元の scaffold を使うときだけ使える。
- 以前に `~/.local/bin/new-novelkit-project` を `scripts/new-novelkit-project` へのシンボリックリンクで入れていたなら、リンクを消してから uv で入れる（`rm ~/.local/bin/new-novelkit-project`）。
- オプションの一覧は [tool/README.md](tool/README.md) にある。

## 使い方

### 新しい作品

```bash
new-novelkit-project ~/novels/my-novel --title "仮題" -m "滅びた王国の料理人が、敵国の王の舌を満たして祖国を取り戻す話"
```

- 作品のディレクトリを作り、Claude Code で `/novelkit-bootstrap <コンセプト>` を始める。`-m` を省くと対話でコンセプトを聞く。`--auto`・`--oneshot` を付けると、そのモードで始める。
- スキルは作品のディレクトリの `skills/novelkit/` にコピーされる。手元の scaffold を使い `--link` を付けると、scaffold へのシンボリックリンクになる（scaffold の更新がすぐ反映される）。コピーの作品は `new-novelkit-project update` で新しい版にする。
- 立ち上げが終わったら `/novelkit-all` で最初の章から進める。`/novelkit-all all --auto` で全章を無人で進めることもできる。

### 既存の作品に取り込む

```bash
new-novelkit-project ~/novels/existing --adopt
```

- 既存のファイルは上書きしない。`.gitignore` は、足りない行だけを末尾に足す。追加したファイルを確かめてからコミットする。
- `.claude/skills/` などに同名のスキル（別の版をコピーで入れていたものなど）があれば残し、`CONFLICT` として表示する。novelkit 版に揃えるなら、既存のものを消してから、手元の scaffold の `python3 scripts/new_project.py --relink <作品のディレクトリ>` で張り直す。
- 既存の `CLAUDE.md` などは上書きしないので、表示された行（`@.kiro/steering/novel-writing.md` など）を足す。
- `.novelkit/config.yaml` の `paths` を既存の配置に合わせる。ファイルは動かさない。合わせた後に `python3 skills/novelkit/novelkit-status/scripts/novelkit.py init` を実行すると、足りないディレクトリだけを作る。
- `/novelkit-bootstrap --adopt` で、既存の資料から足りない成果物だけを作る（`--auto`・`--oneshot` と組み合わせられる）。
  - 既存の資料を探し、W1〜W10 ごとに「移し替える / 完了として記録 / 新しく作る / 飛ばす」を `docs/adopt-plan.md` に書いて合意してから進める。
  - 文体の決まりは既存の決まりと本文から作り（`novelkit-constitution` の取り込み）、設定資料は `novelkit-canon --adopt` でフロントマターを足して正典にする。
  - 書き終えた章は、章仕様とシーン台帳を本文から逆起こしし、台帳の `出力:` で既存の本文を指す。本文は書き換えない（フロントマターを足すのも作者の承認を得てから）。
- 既存の本文だけを先に診断するには、次を実行する。

  ```bash
  python3 skills/novelkit/novelkit-check/scripts/check.py --draft-dir <本文のディレクトリ> --only prose,length --metrics
  ```

### 進捗の確認

```bash
python3 skills/novelkit/novelkit-status/scripts/novelkit.py status     # 章ごとの進捗
python3 skills/novelkit/novelkit-status/scripts/novelkit.py handover   # 引き継ぎ書
```

または `/novelkit-status` を実行する。

## ディレクトリ構成（scaffold）

```text
.
├── README.md
├── CLAUDE.md / AGENTS.md / GEMINI.md   # .kiro/steering を読むよう指示するだけ
├── .kiro/steering/                     # エージェント共通ルールの正本
│   ├── language.md                     #   応答と成果物は日本語（本文の文体は作品の文体の決まりに従う）
│   └── novel-writing.md                #   novelkit の工程とルール
├── .claude/skills/ .agents/skills/ .kiro/skills/   # → skills/novelkit/* へのシンボリックリンク
├── skills/novelkit/                    # スキルの本体（21 本）
│   ├── novelkit-status/scripts/        #   novelkit.py（進捗・文脈パック・引き継ぎ書・検索の予算）、nklib.py（共通ライブラリ）、count_search.py（フック）
│   ├── novelkit-review/scripts/        #   phrases.py（類似性軸の検索候補）
│   └── novelkit-check/scripts/         #   check.py（機械検証）
├── scripts/
│   ├── new_project.py                  # 作品のディレクトリを作る・既存作品に取り込む（--adopt）・リンクを張り直す（--relink）
│   └── new-novelkit-project            # 手元の scaffold から使うときの入口（本体は tool/）
└── tool/                               # uv で入れるコマンド new-novelkit-project（作成・取り込み・update）とテスト
```

## 作品のディレクトリ構成

```text
.novelkit/config.yaml          # パスの対応、1 話の字数、文章の検査のしきい値、文脈パックの設定
.novelkit/memory/constitution.md   # 文体の決まり（最上位の規範）
docs/concept/                  # seed.md、direction.md、premises.md、backlog.md（ネタ帳）
docs/adopt-plan.md             # 既存の作品への取り込みの計画（novelkit-bootstrap --adopt）
docs/research/                 # wide.md、deep/、anachronism.md
docs/plot/                     # synopsis.md、structure.md、promises.md（伏線台帳）、threads.md（筋の台帳）
canon/                         # 正典（1 項目 1 ファイル。フロントマターに ai / reveal_from / born など）
chapters/<NN>-<slug>/          # spec.md（章仕様）、scenes.md（シーン台帳）、state.md、summaries.md、reviews/
draft/<NN>/                    # 本文（フロントマターに status と ai）
publish/                       # 公開・応募の準備
handover/                      # 引き継ぎ書
```

## 取り入れた手法

| 工程 | 手法 |
|---|---|
| 種 | what if（スティーヴン・キング）、ログラインの 4 条件（Blake Snyder）、エレベーターピッチ |
| 調査 | comp titles の選び方（Jane Friedman）、トロープの扱い方（TV Tropes）、KJ 法、一次資料と二次資料（国立国会図書館）、実在モデルの点検（「宴のあと」「石に泳ぐ魚」事件） |
| 方向性 | ジャンルの約束事と必須シーン（Story Grid）、SCAMPER、マンダラート |
| 壁打ち | ジャンル別の小説家エージェント（`~/.myai/sparring`） |
| プロット | スノーフレーク法、三幕構成、Save the Cat、7 ポイント、起承転結、序破急、ヒーローズ・ジャーニー、キャラクターアーク（K.M. Weiland）、Promise/Progress/Payoff（Sanderson）、MICE Quotient |
| 設定 | series bible、Codex の文脈投入（Novelcrafter）、作中の時系列と掲載順の分離（Aeon Timeline）、スタイルシート（copy edit） |
| アウトライン | Story Grid のシーンの台帳（価値の変化）、シーンとシークエル（Dwight Swain）、ハコ書きと柱（シナリオ） |
| 執筆 | 状態の記録（スクリプトスーパーバイザー）、過去の話は要約・直前は本文で渡す |
| レビュー | 編集の段階（developmental → line → copy → 校正）、ベータリーダー、校閲、類似作品の検索と、アイデアと表現の区別（文化庁「著作権テキスト」、江差追分事件）、文章の指標（Novel Supporter など） |
| 公開 | 投稿サイト・公募の AI 利用の規定（実行のたびに公式で確かめる） |
