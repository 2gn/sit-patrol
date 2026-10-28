# SIT Patrol (芝浦工業大学 GitHub 監視トラッカー)

芝浦工業大学（`shibaura-it.ac.jp`）に関連する「新規公開リポジトリ（OSS）」を GitHub Search API で定期的に巡回・自動検知し、RSSリーダーで購読できるサーバーレス監視トラッカーです。

外部サーバーやデータベースを持たず、GitHub Actions と Gitブランチ（`main` と `data`）のみで状態管理と配信を完結させます。

---

## 全体アーキテクチャ

* **ロジック管理 (`main` ブランチ):**
  * `config.yml`: 検索対象ドメインおよびキーワードの定義
  * `src/tracker.py`: GitHub Search API の実行、`index.json` との突合、README取得、`rss.xml` 生成
  * `.github/workflows/update.yml`: GitHub Actions による3時間おきの自動定期実行
* **状態・データ永続化 (`data` ブランチ):**
  * `index.json`: 処理済みリポジトリURL/ID（差分検知データベース）
  * `rss.xml`: RSSリーダー向け配信フィード（RSS 2.0 準拠）

---

## CLIベースの構築・デプロイ手順

ターミナル上ですべて完結する4ステップです。

### 1. リポジトリの初期化と作成
```bash
# git 初期化と初回コミット
git init
git checkout -b main
git add .
git commit -m "feat: initial commit for sit-patrol"

# GitHub に Public リポジトリとして作成 & プッシュ
gh repo create sit-patrol --public --source=. --remote=origin --push
```

### 2. Personal Access Token (PAT) の登録
GitHub Search API のレート制限（未認証: 10回/分 → 認証済: 30回/分）を緩和するため、GitHub Actions 用の Secret にトークンを登録します。

```bash
# GitHub CLI のトークン、または別途作成した PAT を登録
gh secret set GH_PAT -b "$(gh auth token)"
```

### 3. データ保存用ブランチ (`data`) の初期化
コードの変更履歴とデータの更新履歴を分離するため、履歴を持たない孤立（orphan）ブランチを作成し、空の初期状態ファイルをプッシュします。

```bash
# orphan ブランチの作成
git checkout --orphan data

# main ブランチのファイルをインデックスからクリア
git rm -rf .

# 初期状態ファイルの作成
echo '{"version": 1, "last_updated": null, "seen_ids": [], "items": []}' > index.json
touch rss.xml

# コミットとプッシュ
git add index.json rss.xml
git commit -m "chore: initialize state files for patrol feed"
git push -u origin data

# main ブランチに戻る
git checkout main
```

### 4. 動作確認とRSS購読
GitHub Actions のワークフローをCLIから手動実行し、初回のインデックス作成とRSSフィード生成を行います。

```bash
# ワークフローを手動キック
gh workflow run update.yml

# 実行状態の確認
gh run watch
```

完了後、生成された `rss.xml` の Raw URL を手元のRSSリーダーに登録します：
```
https://raw.githubusercontent.com/<あなたのGitHubユーザー名>/sit-patrol/data/rss.xml
```

---

## 設定のカスタマイズ (`config.yml`)

監視するクエリや配信フィードの設定は `config.yml` で変更可能です：

```yaml
feed:
  title: "SIT Patrol (芝浦工業大学 関連リポジトリ)"
  description: "芝浦工業大学に関連する新規公開GitHubリポジトリ（OSS）の自動検知フィード"
  link: "https://github.com/2gn/sit-patrol"
  max_items: 50

queries:
  - id: "domain-search"
    name: "ドメイン検索 (shibaura-it.ac.jp)"
    query: "shibaura-it.ac.jp in:name,description,readme"
    sort: "created"
    order: "desc"

  - id: "keyword-kanji"
    name: "大学名キーワード検索 (芝浦工業大学)"
    query: '"芝浦工業大学" in:name,description,readme'
    sort: "created"
    order: "desc"
```

---

## ローカル開発とテスト

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 単体テストの実行
python -m unittest discover tests

# ドライラン実行 (ファイルを変更せずAPI呼び出しテスト)
python -m src.tracker --config config.yml --dry-run
```
