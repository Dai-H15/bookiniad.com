# Python 3.13の公式イメージを使用
FROM python:3.13-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        sqlite3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# 静的ファイルを収集するためのディレクトリを作成
RUN mkdir -p staticfiles

# データベースマイグレーションを実行
RUN python manage.py collectstatic --noinput
RUN python manage.py migrate

# サンプルデータを設定（失敗してもビルド継続）
RUN python manage.py setup_sample_data || true
RUN python manage.py create_admin || true

# ポート8000を公開
EXPOSE 8000

# 非rootユーザーを作成してセキュリティを向上
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Gunicornを使用してDjangoアプリケーションを起動
CMD ["uvicorn", "--host", "0.0.0.0","--port", "8000", "settings.asgi:application"]