# BookINIAD.com - 旅行予約サイト

AIエージェント比較機能付きの旅行予約サイトです。

## 機能

- 宿泊施設の検索・予約
- 航空券の検索・予約
- 旅行パッケージの提案
- 宿泊人数を考慮した価格計算
- 日付に基づく空き状況管理

## Docker での実行

### 本番環境での実行

```bash
# イメージをビルド
docker-compose build

# アプリケーションを起動
docker-compose up
```

アプリケーションは http://localhost:8000 でアクセスできます。

### 開発環境での実行

```bash
# 開発用のサービスを起動
docker-compose --profile dev up web-dev
```

開発環境は http://localhost:8001 でアクセスできます。

## ローカル開発

```bash
# 依存関係をインストール
pip install -r requirements.txt

# データベースマイグレーション
python manage.py migrate

# サンプルデータを設定
python manage.py setup_sample_data

# 開発サーバーを起動
python manage.py runserver
```

## 機能説明

### 予約システム
- 宿泊人数を考慮した価格計算
- 日付に基づく空き状況の確認
- 自動的な日付入力
- リアルタイム価格更新

### データ管理
- JSONフィクスチャベースのデータ読み込み
- 空き状況データの自動生成
- 管理コマンドによるデータセットアップ
