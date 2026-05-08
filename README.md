# YokoKid

横浜の子ども向けイベントを集約する個人運営の Web サービス。

- **公開 URL**: デプロイ後に追記
- **対象エリア**: 横浜市（v1.1 で関東広域へ拡大予定）
- **更新頻度**: GitHub Actions が日次でクローラを実行

## 構成

```
yokokid/
├── public/             # 静的サイト（Vercel が配信）
│   ├── index.html      # メイン一覧 + フィルタ UI
│   ├── app.js          # Alpine.js コンポーネント
│   ├── about.html, terms.html, privacy.html
│   └── data/events.json  # クローラの出力。フロントが fetch する
├── crawler/            # Python クローラ
│   ├── crawl.py        # エントリーポイント
│   ├── normalize.py    # 日付・年齢・料金のヒューリスティック
│   └── sources/        # 1ソース1モジュール
└── .github/workflows/crawl.yml  # 日次 cron
```

## ローカル開発

```bash
# 依存をインストール
python3 -m venv .venv
.venv/bin/pip install -r crawler/requirements.txt

# クローラ実行（events.json を更新）
.venv/bin/python -m crawler.crawl

# ローカルプレビュー（Python 標準サーバー）
cd public && python3 -m http.server 8000
# → http://localhost:8000/
```

## 実装済みソース（Phase 0）

| ソース | 状態 |
|---|---|
| はまぎん こども宇宙科学館 | ✅ 実装 |
| パマトコ（横浜市子育て応援サイト） | ⏳ v1.1 |
| アンパンマンこどもミュージアム横浜 | ⏳ v1.1 |
| 横浜市立図書館 | ⏳ v1.1 |
| 横浜市西区役所 | ⏳ v1.1 |

## 新規ソースの追加

1. `crawler/sources/<name>.py` を新規作成。`META: SourceMeta` と `fetch_events(client) -> list[dict]` をエクスポート
2. `crawler/sources/__init__.py` の `ALL_SOURCES` に追加
3. ローカルで `python -m crawler.crawl` を実行し動作確認

## デプロイ手順

### 1. GitHub にリポジトリを作成

ブラウザで [github.com/new](https://github.com/new) を開き、

- Repository name: `yokokid`
- Public/Private: お好みで（公開でも秘密情報なし）
- **README / .gitignore / license は追加しない**（ローカルに既存）

「Create repository」をクリック。

### 2. ローカルから push

```bash
cd "/Users/kenta/Desktop/Claude code/yokokid"
git add .
git commit -m "Initial YokoKid commit"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/yokokid.git
git push -u origin main
```

### 3. Vercel を接続

1. [vercel.com](https://vercel.com) に GitHub アカウントでログイン
2. 「Add New…」→「Project」
3. 「Import Git Repository」一覧から `yokokid` を選択
4. 設定:
   - Framework Preset: **Other**
   - Root Directory: そのまま
   - Build Command / Output Directory: `vercel.json` 側で設定済みなので変更不要
5. 「Deploy」をクリック → 約30秒で `yokokid-xxx.vercel.app` の URL が発行される

### 4. GitHub Actions の日次クロールを有効化

1. リポジトリの「Actions」タブを開き、ワークフローの初回実行を承認
2. 「Crawl events」ワークフローを開き、「Run workflow」で初回手動実行
3. 以降、毎日 13:00 JST に自動実行され、変更があれば `events.json` を自動コミット → Vercel が再デプロイ

### トラブルシュート

- **GitHub Actions の `git push` で 403**: リポジトリ Settings → Actions → General →「Workflow permissions」を「Read and write permissions」に変更
- **Vercel デプロイで 404**: `vercel.json` の `outputDirectory: "public"` が反映されているか確認

## ロードマップ

- v1.0（公開時）: 横浜市の主要1ソースを集約。フィルタ・条件保存
- v1.1: 残り4ソースを実装、児童館・図書館の小粒イベントを収録、LINE プッシュ通知
- v1.2: 距離フィルタ（自宅起点）、地図表示
- v2.0: 関東1都6県へ拡大、Google AdSense 検討

## ライセンス

ソースコードは MIT。掲載イベント情報の著作権は各主催者に帰属します。
