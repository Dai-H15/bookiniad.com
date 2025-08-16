from django.db import models

# Create your models here.


# 宿泊施設に関する情報を集約するモデル
class Accommodations(models.Model):
    name = models.CharField(
        max_length=30,
        verbose_name="宿泊施設名"
    )
    rank = models.IntegerField(
        default=0,
        verbose_name="ランク（星数）"
    )
    location = models.CharField(
        max_length=100,
        verbose_name="所在地"
    )
    description = models.TextField(
        blank=True,
        verbose_name="説明"
    )
    amenities = models.JSONField(
        default=list,
        verbose_name="設備・アメニティ"
    )
    price_per_night = models.IntegerField(
        default=10000,
        verbose_name="1泊あたりの料金"
    )
    image_url = models.URLField(
        blank=True,
        verbose_name="画像URL"
    )
    total_rooms = models.IntegerField(
        default=50,
        verbose_name="総部屋数"
    )


# 宿泊施設の空室管理モデル
class AccommodationAvailability(models.Model):
    accommodation = models.ForeignKey(
        Accommodations,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    date = models.DateField(
        verbose_name="日付"
    )
    available_rooms = models.IntegerField(
        verbose_name="空室数"
    )
    
    class Meta:
        unique_together = ['accommodation', 'date']
        indexes = [
            models.Index(fields=['accommodation', 'date']),
        ]
    
    def __str__(self):
        return f"{self.accommodation.name} - {self.date} - {self.available_rooms}室"


class Air(models.Model):
    FLIGHT_TYPES = [
        ('domestic', '国内線'),
        ('international', '国際線'),
    ]
    
    name = models.CharField(
        max_length=120,
        verbose_name="航空会社名"
    )
    flight_number = models.CharField(
        max_length=20,
        verbose_name="便名"
    )
    flight_type = models.CharField(
        max_length=20,
        choices=FLIGHT_TYPES,
        default='domestic',
        verbose_name="便種別"
    )
    place_from = models.CharField(
        max_length=20,
        verbose_name="出発地"
    )
    place_to = models.CharField(
        max_length=20,
        verbose_name="到着地"
    )
    departure_time = models.DateTimeField(
        verbose_name="出発日時"
    )
    arrival_time = models.DateTimeField(
        verbose_name="到着日時"
    )
    fee = models.IntegerField(
        verbose_name="料金"
    )
    available_seats = models.IntegerField(
        default=100,
        verbose_name="空席数"
    )


# 航空券の空席管理モデル
class FlightAvailability(models.Model):
    flight = models.ForeignKey(
        Air,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    date = models.DateField(
        verbose_name="日付"
    )
    available_seats = models.IntegerField(
        verbose_name="空席数"
    )
    
    class Meta:
        unique_together = ['flight', 'date']
        indexes = [
            models.Index(fields=['flight', 'date']),
        ]
    
    def __str__(self):
        return f"{self.flight.flight_number} - {self.date} - {self.available_seats}席"


# 予約を管理するモデル
class Booking(models.Model):
    reservation_number = models.AutoField(
        unique=True,
        null=False,
        help_text="予約番号",
        verbose_name="予約番号",
        primary_key=True
    )
    from_date = models.DateTimeField(
        blank=False,
        null=False,
        verbose_name="到着予定日時"
    )
    to_date = models.DateTimeField(
        blank=False,
        null=False,
        verbose_name="出発予定時刻",
    )
    num_of_people = models.IntegerField(
        default=1
    )
    total_fee = models.IntegerField(
        blank=False,
        null=False,
        default=1
    )
    place = models.CharField(
        max_length=30
    )
    accommodations = models.ForeignKey(
        Accommodations,
        on_delete=models.CASCADE
    )
    air = models.ManyToManyField(
        Air
    )


# 宿泊施設に設定する予約枠のテンプレを登録するモデル
class StayTemplate(models.Model):
    max_num_of_people = models.IntegerField(
    )
    date = models.DateField(
        auto_now=True
    )
    fee_per_people = models.IntegerField(
        default=1,
    )
    discount_rate = models.IntegerField(
    )


# 会話セッションを管理するモデル
class ChatSession(models.Model):
    SESSION_TYPES = [
        ('ai_agent', 'AIエージェント'),
        ('ai_assistant', 'AIアシスタント'),
        ('rule_bot', 'ルールベースBot'),
    ]
    
    session_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="セッションID"
    )
    session_type = models.CharField(
        max_length=20,
        choices=SESSION_TYPES,
        verbose_name="セッションタイプ"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="アクティブ状態"
    )


# 会話メッセージを記録するモデル
class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('user', 'ユーザー'),
        ('ai_agent', 'AIエージェント'),
        ('ai_assistant', 'AIアシスタント'),
        ('rule_bot', 'ルールベースBot'),
    ]
    
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPES,
        verbose_name="メッセージタイプ"
    )
    content = models.TextField(
        verbose_name="メッセージ内容"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="送信日時"
    )
    # AIの判断プロセスを記録
    reasoning_process = models.JSONField(
        null=True,
        blank=True,
        verbose_name="推論プロセス"
    )


# 検索条件を記録するモデル
class SearchCondition(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='search_conditions'
    )
    departure_place = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="出発地"
    )
    destination_place = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="目的地"
    )
    departure_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="出発日"
    )
    return_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="帰国日"
    )
    num_of_people = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="人数"
    )
    budget_min = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="最低予算"
    )
    budget_max = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="最高予算"
    )
    preferences = models.JSONField(
        null=True,
        blank=True,
        verbose_name="好み・要望"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )


# 旅行パッケージを管理するモデル
class TravelPackage(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="パッケージ名"
    )
    description = models.TextField(
        verbose_name="説明"
    )
    total_price = models.IntegerField(
        verbose_name="総額"
    )
    outbound_flight = models.ForeignKey(
        Air,
        on_delete=models.CASCADE,
        related_name='outbound_packages',
        verbose_name="往路フライト",
        null=True,
        blank=True
    )
    return_flight = models.ForeignKey(
        Air,
        on_delete=models.CASCADE,
        related_name='return_packages',
        verbose_name="復路フライト",
        null=True,
        blank=True
    )
    accommodation = models.ForeignKey(
        Accommodations,
        on_delete=models.CASCADE,
        verbose_name="宿泊施設",
        null=True,
        blank=True
    )
    stay_duration = models.IntegerField(
        verbose_name="宿泊日数"
    )
    is_available = models.BooleanField(
        default=True,
        verbose_name="予約可能"
    )


# AIエージェント/アシスタント/Botのパフォーマンスを記録
class PerformanceMetrics(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='performance_metrics'
    )
    response_time = models.FloatField(
        verbose_name="応答時間（秒）"
    )
    successful_booking = models.BooleanField(
        default=False,
        verbose_name="予約成功"
    )
    user_satisfaction = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],
        verbose_name="ユーザー満足度（1-5）"
    )
    number_of_turns = models.IntegerField(
        verbose_name="会話ターン数"
    )
    task_completion_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name="タスク完了率"
    )
    error_count = models.IntegerField(
        default=0,
        verbose_name="エラー回数"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )


# システム応答のログを記録
class SystemResponse(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='system_responses'
    )
    intent_detected = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="検出されたインテント"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name="信頼度スコア"
    )
    api_call_info = models.JSONField(
        null=True,
        blank=True,
        verbose_name="API呼び出し情報"
    )
    processing_time = models.FloatField(
        verbose_name="処理時間"
    )
    response_generated = models.TextField(
        verbose_name="生成された応答"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True
    )
