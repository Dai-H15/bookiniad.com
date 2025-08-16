# bookiniad.com データベース初期化ガイド

## 概要
このドキュメントでは、bookiniad.comサイトのデータベースに初期データを投入する方法を説明します。

## 方法1: Django Management Command（推奨）

### 基本的な使用方法
```bash
# サンプルデータを作成
python manage.py setup_sample_data

# 既存データを削除してから作成
python manage.py setup_sample_data --clear

# ヘルプを表示
python manage.py setup_sample_data --help
```

### 作成されるデータ
- **宿泊施設**: 6件（東京グランドホテル、大阪ビジネスホテル、沖縄リゾートホテル等）
- **航空券**: 10件（JAL、ANA、スカイマーク等の国内線・国際線）
- **旅行パッケージ**: 7件（航空券+宿泊施設のセット）

## 方法2: Django Fixtures

### Fixtures の場所
- `main/fixtures/accommodations.json` - 宿泊施設データ
- `main/fixtures/air.json` - 航空券データ
- `main/fixtures/travel_packages.json` - 旅行パッケージデータ

### 使用方法
```bash
# 個別にロード
python manage.py loaddata accommodations
python manage.py loaddata air
python manage.py loaddata travel_packages

# 一括ロード
python manage.py loaddata accommodations air travel_packages
```

## 管理者ユーザーの作成

### 自動作成コマンド
```bash
python manage.py create_admin
```

作成されるユーザー情報:
- **ユーザー名**: admin
- **パスワード**: admin123
- **メール**: admin@bookiniad.com

### 手動作成
```bash
python manage.py createsuperuser
```

## Django管理サイトへのアクセス

1. 開発サーバーを起動
   ```bash
   python manage.py runserver
   ```

2. ブラウザでアクセス
   ```
   http://127.0.0.1:8000/admin/
   ```

3. 管理者アカウントでログイン

## 管理サイトの機能

### 宿泊施設管理 (Accommodations)
- ホテルの基本情報、ランク、設備情報を管理
- 検索・フィルタリング機能
- 設備数の表示、画像有無の確認

### 航空券管理 (Air)
- 航空会社、便名、路線情報を管理
- 出発日時でのフィルタリング
- 国内線・国際線の分類

### 旅行パッケージ管理 (Travel Package)
- 航空券と宿泊施設のセット商品
- 料金設定、空室状況管理
- 往復便の設定（片道も可能）

### AI関連データ管理
- **Chat Sessions**: AIとの会話セッション
- **Chat Messages**: 会話履歴
- **Performance Metrics**: AIシステムの性能データ
- **System Response**: システム応答ログ

## トラブルシューティング

### エラー: "NOT NULL constraint failed"
TravelPackageで航空券や宿泊施設が必須フィールドの場合に発生。
解決方法: モデルにnull=True, blank=Trueを追加してマイグレーション。

### データの完全リセット
```bash
# データベースファイルを削除
rm db.sqlite3

# 新しいデータベースを作成
python manage.py migrate

# サンプルデータを投入
python manage.py setup_sample_data

# 管理者ユーザーを作成
python manage.py create_admin
```

## データの確認

### コマンドライン
```bash
# データ件数の確認
python manage.py shell
>>> from main.models import Accommodations, Air, TravelPackage
>>> print(f"宿泊施設: {Accommodations.objects.count()}件")
>>> print(f"航空券: {Air.objects.count()}件")
>>> print(f"パッケージ: {TravelPackage.objects.count()}件")
```

### 管理サイト
- 各モデルのリスト画面で件数とデータを確認
- 検索・フィルタ機能でデータの整合性をチェック

## データのカスタマイズ

### 独自データの追加
1. 管理サイトから手動追加
2. Fixture ファイルを編集
3. Management Command を修正

### 本番環境での注意
- パスワードを変更する
- DEBUG = False に設定
- SECRET_KEY を環境変数で管理
- データベースをSQLiteから変更を検討
