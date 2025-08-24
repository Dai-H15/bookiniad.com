import json
import os
import sys
from datetime import datetime

# Django設定の初期化（インポート前に実行）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.settings')

import django
django.setup()

from openai import OpenAI
from django.db.models import Q
from main.models import Air, Accommodations, Booking

# グローバル変数は削除し、クラス内で管理


def search_air(place_from: str, place_to: str, departure_date: str = "") -> str:
    """航空券をデータベースから検索（出発日未定でも対応）"""
    try:
        query = Air.objects.filter(
            place_from__icontains=place_from,
            place_to__icontains=place_to
        )
        
        # 出発日が指定されている場合
        if departure_date:
            try:
                search_date = datetime.strptime(departure_date, '%Y-%m-%d').date()
                query = query.filter(departure_time__date=search_date)
            except ValueError:
                # 日付形式が正しくない場合はすべての便を表示
                pass
        
        # 日付順でソート（最新の便から）
        flights = query.order_by('departure_time')[:10]  # 最大10件
        
        if not flights:
            # 便が見つからない場合、条件を緩和して検索
            fallback_query = Air.objects.filter(
                Q(place_from__icontains=place_from) | Q(place_to__icontains=place_to)
            )
            flights = fallback_query.order_by('departure_time')[:5]
            
            if not flights:
                return f"{place_from}から{place_to}への航空券が見つかりませんでした。別の路線をお探しください。"
        
        results = []
        for flight in flights:
            # 出発日が未定の場合は複数の日程オプションを表示
            result_item = {
                "便名": flight.flight_number,
                "航空会社": flight.name,
                "出発地": flight.place_from,
                "目的地": flight.place_to,
                "出発時刻": flight.departure_time.strftime('%Y-%m-%d %H:%M'),
                "到着時刻": flight.arrival_time.strftime('%Y-%m-%d %H:%M'),
                "料金": f"¥{flight.fee:,}",
                "空席数": flight.available_seats,
                "便種別": flight.get_flight_type_display()
            }
            
            # 出発日が未定の場合は、曜日情報も追加
            if not departure_date:
                weekday_names = ['月', '火', '水', '木', '金', '土', '日']
                weekday = weekday_names[flight.departure_time.weekday()]
                result_item["曜日"] = weekday
                result_item["出発日程"] = f"{flight.departure_time.strftime('%m月%d日')}({weekday})"
            
            results.append(result_item)
        
        # 出発日未定の場合の追加メッセージ
        additional_info = ""
        if not departure_date:
            additional_info = "\n\n※出発日が未定のため、利用可能な便をご案内しています。具体的な日程が決まりましたら、お知らせください。"
        
        return json.dumps(results, ensure_ascii=False, indent=2) + additional_info
    
    except Exception as e:
        return f"検索中にエラーが発生しました: {str(e)}"


def search_accommodations(location: str, checkin_date: str = "", checkout_date: str = "", guests: int = 2) -> str:
    """宿泊施設をデータベースから検索（日程未定でも対応、施設名にも地名検索対応）"""
    try:
        # 地名をキーワードに分割して検索精度を向上
        location_keywords = location.replace(',', ' ').replace('、', ' ').split()
        
        # 基本検索：locationとnameの両方で包括的に検索
        query = Accommodations.objects.all()
        
        # 各キーワードで OR検索を行う
        search_conditions = Q()
        
        for keyword in location_keywords:
            keyword = keyword.strip()
            if keyword:  # 空文字列でない場合のみ
                # location、name、descriptionの各フィールドで検索
                keyword_condition = (
                    Q(location__icontains=keyword) |
                    Q(name__icontains=keyword) |
                    Q(description__icontains=keyword)
                )
                search_conditions |= keyword_condition
        
        # 検索条件を適用
        if search_conditions:
            query = query.filter(search_conditions)
        else:
            # キーワードがない場合は元の検索方法を使用
            query = query.filter(
                Q(location__icontains=location) | Q(name__icontains=location)
            )
        
        # 宿泊人数による簡易フィルタ（部屋数で判断）
        if guests > 4:
            query = query.filter(total_rooms__gte=2)  # 大人数の場合は複数部屋ある施設を優先
        
        # 関連度順でソート（より多くのキーワードにマッチするものを優先）
        accommodations = query.order_by('price_per_night')[:10]  # 最大10件、料金順
        
        if not accommodations:
            # 条件を緩和して再検索（単一キーワードでの検索）
            fallback_conditions = Q()
            for keyword in location_keywords:
                keyword = keyword.strip()
                if keyword:
                    fallback_conditions |= (
                        Q(location__icontains=keyword) |
                        Q(name__icontains=keyword)
                    )
            
            if fallback_conditions:
                fallback_query = Accommodations.objects.filter(fallback_conditions)
                accommodations = fallback_query.order_by('price_per_night')[:5]
            
            if not accommodations:
                return f"{location}周辺で宿泊施設が見つかりませんでした。別の地域名や施設名をお試しください。"
        
        results = []
        for acc in accommodations:
            # 宿泊日数と料金の計算
            nights = 1
            total_cost = acc.price_per_night * nights * guests
            
            # チェックイン・チェックアウト日が指定されている場合
            if checkin_date and checkout_date:
                try:
                    checkin = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                    checkout = datetime.strptime(checkout_date, '%Y-%m-%d').date()
                    if checkout > checkin:
                        nights = (checkout - checkin).days
                        total_cost = acc.price_per_night * nights * guests
                except ValueError:
                    # 日付が正しくない場合はデフォルト値を使用
                    pass
            
            # 検索キーワードとのマッチ情報を追加
            match_info = []
            for keyword in location_keywords:
                keyword = keyword.strip().lower()
                if keyword:
                    if keyword in acc.location.lower():
                        match_info.append(f"所在地: {keyword}")
                    if keyword in acc.name.lower():
                        match_info.append(f"施設名: {keyword}")
                    if keyword in acc.description.lower():
                        match_info.append(f"説明: {keyword}")
            
            # 宿泊施設情報を構築
            result_item = {
                "施設名": acc.name,
                "所在地": acc.location,
                "ランク": f"{'⭐' * acc.rank} ({acc.rank}つ星)",
                "1泊料金": f"¥{acc.price_per_night:,}/泊",
                "説明": acc.description[:100] + "..." if len(acc.description) > 100 else acc.description,
                "設備": acc.amenities[:5] if acc.amenities else [],
                "総部屋数": acc.total_rooms
            }
            
            # マッチ情報を追加（デバッグ用、必要に応じて表示）
            if match_info:
                result_item["検索マッチ"] = ", ".join(match_info)
            
            # 日程が指定されている場合の料金計算
            if checkin_date and checkout_date:
                result_item["宿泊期間"] = f"{nights}泊"
                result_item["総料金"] = f"¥{total_cost:,} ({guests}名)"
            else:
                # 日程未定の場合のサンプル料金表示
                result_item["料金例"] = {
                    "1泊": f"¥{acc.price_per_night * guests:,} ({guests}名)",
                    "2泊": f"¥{acc.price_per_night * 2 * guests:,} ({guests}名)",
                    "3泊": f"¥{acc.price_per_night * 3 * guests:,} ({guests}名)"
                }
            
            # 予約の目安情報
            if not checkin_date:
                result_item["予約のご案内"] = "具体的な宿泊日程が決まりましたら、空室状況をご確認いたします。"
            
            results.append(result_item)
        
        # 日程未定の場合の追加メッセージ
        additional_info = ""
        if not checkin_date or not checkout_date:
            additional_info = f"\n\n※{location}の宿泊施設をご案内しています。具体的な宿泊日程が決まりましたら、より詳細な料金と空室状況をお調べいたします。"
            additional_info += f"\n※表示料金は{guests}名様でのご利用を想定しています。"
        
        return json.dumps(results, ensure_ascii=False, indent=2) + additional_info
    
    except Exception as e:
        return f"検索中にエラーが発生しました: {str(e)}"


def get_travel_recommendations(destination: str, budget: int = None, duration: int = None, departure_date: str = "") -> str:
    """旅行先のおすすめ情報を提供（日程未定でも対応）"""
    try:
        # 航空券と宿泊施設の両方を検索
        flight_query = Air.objects.filter(place_to__icontains=destination)
        
        # 出発日が指定されている場合
        if departure_date:
            try:
                search_date = datetime.strptime(departure_date, '%Y-%m-%d').date()
                flight_query = flight_query.filter(departure_time__date=search_date)
            except ValueError:
                pass
        
        flights = flight_query.order_by('fee')[:5]  # 料金の安い順
        accommodations = Accommodations.objects.filter(location__icontains=destination).order_by('price_per_night')[:5]
        
        recommendations = {
            "目的地": destination,
            "おすすめフライト": [],
            "おすすめ宿泊施設": [],
            "予算目安": {},
            "旅行プランニング情報": {}
        }
        
        # フライト情報
        for flight in flights:
            recommendations["おすすめフライト"].append({
                "便名": flight.flight_number,
                "航空会社": flight.name,
                "料金": f"¥{flight.fee:,}",
                "所要時間": "約2時間"  # 実際の計算が必要な場合は追加
            })
        
        # 宿泊施設情報
        total_acc_cost = 0
        for acc in accommodations:
            acc_nights = duration or 2
            acc_cost = acc.price_per_night * acc_nights
            total_acc_cost += acc_cost
            
            recommendations["おすすめ宿泊施設"].append({
                "施設名": acc.name,
                "ランク": f"{acc.rank}つ星",
                "料金": f"¥{acc.price_per_night:,}/泊",
                f"{acc_nights}泊総額": f"¥{acc_cost:,}"
            })
        
        # 予算目安
        if flights and accommodations:
            min_flight = min(flight.fee for flight in flights)
            avg_acc = total_acc_cost // len(accommodations) if accommodations else 0
            total_estimate = min_flight + avg_acc
            
            recommendations["予算目安"] = {
                "最安航空券": f"¥{min_flight:,}",
                "平均宿泊費": f"¥{avg_acc:,}",
                "総額目安": f"¥{total_estimate:,}"
            }
        
        return json.dumps(recommendations, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return f"おすすめ情報の取得中にエラーが発生しました: {str(e)}"


def get_reservation_detail(reservation_number: str) -> str:
    """予約番号に基づいて予約詳細情報を取得"""
    try:
        import uuid
        
        # UUID形式の文字列を適切に処理
        try:
            # 文字列をUUIDオブジェクトに変換して検証
            uuid_obj = uuid.UUID(reservation_number)
            booking = Booking.objects.get(reservation_number=uuid_obj)
        except ValueError:
            # UUID形式でない場合は、文字列として検索を試行
            booking = Booking.objects.get(reservation_number=reservation_number)
        
        # 宿泊日数を計算
        from datetime import date, datetime
        
        checkin_date = None
        checkout_date = None
        nights = 1
        
        if booking.from_date:
            # 日付型に統一して変換
            if isinstance(booking.from_date, datetime):
                checkin_date = booking.from_date.date()
            elif isinstance(booking.from_date, date):
                checkin_date = booking.from_date
            else:
                try:
                    checkin_date = datetime.strptime(str(booking.from_date), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    checkin_date = date.today()
        
        if booking.to_date:
            if isinstance(booking.to_date, datetime):
                checkout_date = booking.to_date.date()
            elif isinstance(booking.to_date, date):
                checkout_date = booking.to_date
            else:
                try:
                    checkout_date = datetime.strptime(str(booking.to_date), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    checkout_date = date.today()
        
        # 宿泊日数計算
        if checkin_date and checkout_date:
            nights = (checkout_date - checkin_date).days
            if nights <= 0:
                nights = 1
        
        # チェックインまでの日数を計算
        days_until_checkin = 0
        if checkin_date:
            days_until_checkin = (checkin_date - date.today()).days
        
        # 航空券情報を取得
        flights = booking.air.all()
        flights_info = []
        flight_total = 0
        
        for flight in flights:
            flight_cost = flight.fee * booking.num_of_people
            flight_total += flight_cost
            
            flights_info.append({
                "便名": flight.flight_number,
                "航空会社": flight.name,
                "出発地": flight.place_from,
                "到着地": flight.place_to,
                "出発日時": flight.departure_time.strftime('%Y年%m月%d日 %H:%M'),
                "到着日時": flight.arrival_time.strftime('%Y年%m月%d日 %H:%M'),
                "料金": f"¥{flight.fee:,}",
                "料金合計": f"¥{flight_cost:,} ({booking.num_of_people}名分)",
                "便種別": flight.get_flight_type_display()
            })
        
        # 宿泊施設情報
        accommodation_total = 0
        accommodation_info = {}
        
        if booking.accommodations:
            accommodation_cost = booking.accommodations.price_per_night * nights * booking.num_of_people
            accommodation_total = accommodation_cost
            
            accommodation_info = {
                "施設名": booking.accommodations.name,
                "所在地": booking.accommodations.location,
                "ランク": f"{'⭐' * booking.accommodations.rank} ({booking.accommodations.rank}つ星)",
                "1泊料金": f"¥{booking.accommodations.price_per_night:,}",
                "宿泊日数": f"{nights}泊",
                "料金合計": f"¥{accommodation_cost:,} ({nights}泊 × {booking.num_of_people}名)",
                "設備": booking.accommodations.amenities[:5] if booking.accommodations.amenities else []
            }
        
        # 正しい合計金額を計算
        calculated_total = accommodation_total + flight_total
        
        # 予約ステータス
        status = "予約確定"
        if days_until_checkin > 0:
            status_detail = f"チェックインまで{days_until_checkin}日"
        elif days_until_checkin == 0:
            status_detail = "本日チェックイン"
        else:
            status_detail = "チェックイン済み"
        
        # 予約詳細を構築
        reservation_detail = {
            "予約番号": str(booking.reservation_number),
            "予約ステータス": status,
            "ステータス詳細": status_detail,
            "お客様情報": {
                "予約人数": f"{booking.num_of_people}名",
                "旅行先": booking.place
            },
            "宿泊情報": accommodation_info if booking.accommodations else "宿泊施設なし",
            "航空券情報": flights_info if flights_info else "航空券なし",
            "日程": {
                "チェックイン": checkin_date.strftime('%Y年%m月%d日') if checkin_date else "未設定",
                "チェックアウト": checkout_date.strftime('%Y年%m月%d日') if checkout_date else "未設定",
                "宿泊日数": f"{nights}泊",
                "チェックインまで": f"{max(0, days_until_checkin)}日"
            },
            "料金詳細": {
                "宿泊料金": f"¥{accommodation_total:,}" if accommodation_total > 0 else "¥0",
                "航空券料金": f"¥{flight_total:,}" if flight_total > 0 else "¥0",
                "合計金額": f"¥{calculated_total:,}",
                "保存済み金額": f"¥{booking.total_fee:,}",
                "金額一致": "はい" if calculated_total == booking.total_fee else "いいえ（人数反映後の金額を表示）"
            }
        }
        
        return json.dumps(reservation_detail, ensure_ascii=False, indent=2)
        
    except Booking.DoesNotExist:
        return f"予約番号「{reservation_number}」の予約情報が見つかりませんでした。正しい予約番号を確認してください。"
    except Exception as e:
        return f"予約詳細の取得中にエラーが発生しました: {str(e)}"


class TravelChatAssistant:
    """旅行予約AIアシスタントクラス - 会話履歴を保持"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key="i9MSQIpMftnMdCuBDtwuS85r4MW2S1CzEZsqxgNkIC81hAjoH5H9JtNDqtMSp4urX4YXVexxM9eTuW6V4UQZ2AQ",
            base_url="https://api.openai.iniad.org/api/v1"
        )
        self.conversation_history = []
        self.system_prompt = """あなたはbookiniad.comの旅行予約AIアシスタントです。
ユーザーの旅行に関する質問や要望に対して、以下の機能を使って最適なサポートを提供してください：

1. 航空券検索: search_air関数を使用
   - 出発日が未定でも検索可能です。その場合は利用可能な便を表示し、日程決定のサポートをしてください
   - 出発日未定の場合は departure_date パラメータを空文字列で指定してください
   
2. 宿泊施設検索: search_accommodations関数を使用
   - チェックイン・チェックアウト日が未定でも宿泊施設の情報を提供できます
   - 日程未定の場合は checkin_date、checkout_date パラメータを空文字列で指定してください
   - 宿泊人数に応じた料金例も表示します
   
3. 旅行おすすめ情報: get_travel_recommendations関数を使用
   - 出発日未定でも総合的な旅行提案が可能です

重要な対応方針：
- 出発日や日程が未定でも積極的に情報提供し、旅行計画のサポートをしてください
- 「いつ頃お考えですか？」「ご希望の時期はありますか？」などの質問で日程決定をサポートしてください
- 曜日別の料金差、季節による変動なども考慮した提案をしてください

応答は日本語で、親切で具体的な情報を提供してください。
価格や日程などの詳細情報も含めて回答してください。
会話の文脈を考慮して、前回の質問や回答を参考にしながら応答してください。"""
    
    def add_to_history(self, role: str, content: str, tool_calls=None, tool_call_id=None, name=None):
        """会話履歴に追加"""
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if tool_call_id:
            message["tool_call_id"] = tool_call_id
        if name:
            message["name"] = name
        self.conversation_history.append(message)
    
    def get_conversation_history(self):
        """会話履歴を取得"""
        return self.conversation_history.copy()
    
    def clear_history(self):
        """会話履歴をクリア"""
        self.conversation_history = []
    
    def get_messages_for_api(self, user_message: str):
        """APIに送信するメッセージリストを構築"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 会話履歴を追加（最新10件まで）
        recent_history = self.conversation_history[-15:] if len(self.conversation_history) > 15 else self.conversation_history
        messages.extend(recent_history)
        
        # 新しいユーザーメッセージを追加
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def chat(self, user_message: str) -> str:
        """メイン関数：ユーザーメッセージに基づいて適切な応答を生成"""
        try:
            # メッセージリストを構築
            messages = self.get_messages_for_api(user_message)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "search_air",
                            "description": "航空券をデータベースから検索します。出発日が未定でも利用可能な便を表示できます。",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "place_from": {
                                        "type": "string",
                                        "description": "出発地（例：東京、大阪）",
                                    },
                                    "place_to": {
                                        "type": "string", 
                                        "description": "目的地（例：沖縄、福岡）",
                                    },
                                    "departure_date": {
                                        "type": "string",
                                        "description": "出発日（YYYY-MM-DD形式、例：2025-08-20）。未定の場合は空文字列を指定。",
                                    }
                                },
                                "required": ["place_from", "place_to"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "search_accommodations",
                            "description": "宿泊施設をデータベースから検索します。チェックイン・チェックアウト日が未定でも宿泊施設の情報を提供できます。地名だけでなく、施設名にも地名が含まれている場合も検索対象となります。",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "宿泊地または施設名に含まれる地名（例：東京、沖縄、大阪、新宿、渋谷、ディズニーランド周辺など）",
                                    },
                                    "checkin_date": {
                                        "type": "string",
                                        "description": "チェックイン日（YYYY-MM-DD形式）。未定の場合は空文字列を指定。",
                                    },
                                    "checkout_date": {
                                        "type": "string",
                                        "description": "チェックアウト日（YYYY-MM-DD形式）。未定の場合は空文字列を指定。",
                                    },
                                    "guests": {
                                        "type": "integer",
                                        "description": "宿泊人数（デフォルト：2名）",
                                    }
                                },
                                "required": ["location"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_travel_recommendations",
                            "description": "旅行先のおすすめ情報と予算目安を提供します。出発日未定でも利用可能です。",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "destination": {
                                        "type": "string",
                                        "description": "旅行先（例：沖縄、北海道）",
                                    },
                                    "budget": {
                                        "type": "integer",
                                        "description": "予算（円）",
                                    },
                                    "duration": {
                                        "type": "integer", 
                                        "description": "旅行日数",
                                    },
                                    "departure_date": {
                                        "type": "string",
                                        "description": "出発日（YYYY-MM-DD形式）。未定の場合は空文字列を指定。",
                                    }
                                },
                                "required": ["destination"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_reservation_detail",
                            "description": "渡された予約番号をもとに予約内容を照会することができます",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "reservation_number": {
                                        "type": "string",
                                        "description": "予約番号（UUID形式または文字列形式）",
                                    }
                                },
                                "required": ["reservation_number"],
                            }
                        }
                    }
                ],
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # ユーザーメッセージを履歴に追加
            self.add_to_history("user", user_message)
            
            # Function callがある場合の処理
            if message.tool_calls:
                # アシスタントメッセージを履歴に追加
                self.add_to_history("assistant", message.content, message.tool_calls)
                
                # すべてのfunction callを実行
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # 関数を実行
                    if function_name == "search_air":
                        function_response = search_air(**function_args)
                    elif function_name == "search_accommodations":
                        function_response = search_accommodations(**function_args)
                    elif function_name == "get_travel_recommendations":
                        function_response = get_travel_recommendations(**function_args)
                    elif function_name == "get_reservation_detail":
                        function_response = get_reservation_detail(**function_args)
                    else:
                        function_response = "未知の関数が呼び出されました。"
                    
                    # Function結果を履歴に追加
                    self.add_to_history("tool", function_response, tool_call_id=tool_call.id, name=function_name)
                
                # 最終的な応答を生成するためのメッセージを構築
                final_messages = self.get_messages_for_api("")
                final_messages.pop()  # 空のユーザーメッセージを削除
                
                final_response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=final_messages
                )
                
                final_content = final_response.choices[0].message.content or "応答の生成に失敗しました。"
                
                # 最終応答を履歴に追加
                self.add_to_history("assistant", final_content)
                
                return final_content
            
            else:
                # Function callがない場合
                response_content = message.content or "応答がありませんでした。"
                
                # 応答を履歴に追加
                self.add_to_history("assistant", response_content)
                
                return response_content
                
        except Exception as e:
            error_message = f"エラーが発生しました: {str(e)}"
            self.add_to_history("assistant", error_message)
            return error_message
    
    def get_conversation_summary(self):
        """会話の要約を取得"""
        if not self.conversation_history:
            return {"status": "会話履歴がありません。"}
        
        user_messages = [msg["content"] for msg in self.conversation_history if msg["role"] == "user"]
        assistant_messages = [msg["content"] for msg in self.conversation_history if msg["role"] == "assistant"]
        
        return {
            "総会話数": len(self.conversation_history),
            "ユーザーメッセージ数": len(user_messages),
            "アシスタントメッセージ数": len(assistant_messages),
            "最新のユーザーメッセージ": user_messages[-1] if user_messages else None,
            "最新のアシスタントメッセージ": assistant_messages[-1] if assistant_messages else None
        }


# 後方互換性のための関数
def travel_chat_assistant(user_message: str) -> str:
    """後方互換性のための関数"""
    if not hasattr(travel_chat_assistant, 'instance'):
        travel_chat_assistant.instance = TravelChatAssistant()
    return travel_chat_assistant.instance.chat(user_message)


# テスト実行用のメイン関数
def main():
    """対話型テスト"""
    print("=== bookiniad.com 旅行AIアシスタント（会話履歴機能付き） ===")
    print("「quit」で終了、「history」で会話履歴表示、「clear」で履歴クリア")
    
    # アシスタントインスタンスを作成
    assistant = TravelChatAssistant()
    
    while True:
        try:
            user_input = input("\nユーザー: ")
            if user_input.lower() in ['quit', 'exit', '終了']:
                break
            elif user_input.lower() == 'history':
                print("\n=== 会話履歴 ===")
                history = assistant.get_conversation_history()
                for i, msg in enumerate(history):
                    role_name = {
                        'user': 'ユーザー',
                        'assistant': 'アシスタント',
                        'tool': 'システム'
                    }.get(msg['role'], msg['role'])
                    print(f"{i+1}. {role_name}: {msg['content'][:100]}...")
                continue
            elif user_input.lower() == 'clear':
                assistant.clear_history()
                print("会話履歴をクリアしました。")
                continue
            elif user_input.lower() == 'summary':
                summary = assistant.get_conversation_summary()
                print("\n=== 会話要約 ===")
                for key, value in summary.items():
                    print(f"{key}: {value}")
                continue
            
            response = assistant.chat(user_input)
            print(f"\nアシスタント: {response}")
            
        except KeyboardInterrupt:
            print("\n\n終了します。")
            break
        except Exception as e:
            print(f"\nエラー: {e}")


if __name__ == "__main__":
    # サンプルテスト（クラスベース）
    print("=== サンプルテスト（会話履歴機能テスト） ===")
    assistant = TravelChatAssistant()
    
    test_messages = [
        "こんにちは！東京から旅行を考えています",
        "沖縄はどうですか？",
        "沖縄への航空券の料金を教えて",
        "沖縄のホテルも探してください"
    ]
    
    for msg in test_messages:
        print(f"\nユーザー: {msg}")
        response = assistant.chat(msg)
        print(f"アシスタント: {response}")
        print("-" * 50)
    
    # 会話履歴の表示
    print("\n=== 会話履歴 ===")
    history = assistant.get_conversation_history()
    for i, msg in enumerate(history):
        role_name = {
            'user': 'ユーザー',
            'assistant': 'アシスタント', 
            'tool': 'システム'
        }.get(msg['role'], msg['role'])
        print(f"{i+1}. {role_name}: {msg['content'][:80]}...")
    
    print("\n=== 会話要約 ===")
    summary = assistant.get_conversation_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    # 対話モード
    main()
