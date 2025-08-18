from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.core.paginator import Paginator
from django.db.models import Q
import json
import uuid
import time
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from main.ai_agents.agent import TravelAgentSystem
from main.ai_agents.bot import handle_rule_bot
from main.ai_agents.assistant import TravelChatAssistant

from .models import (
    Accommodations, Air, Booking, TravelPackage,
    ChatSession, ChatMessage,
    SystemResponse, Cart, CartItem
)

# セッションごとのTravelChatAssistantインスタンスを管理
session_assistants = {}

# AI処理用のスレッドプール（長時間処理のバックグラウンド実行に使用）
AGENT_WORKERS = int(os.environ.get('AGENT_WORKERS', '4'))
_agent_executor = ThreadPoolExecutor(max_workers=AGENT_WORKERS)
AGENT_SYNC_TIMEOUT = float(os.environ.get('AGENT_SYNC_TIMEOUT', '20'))


# トップページ
def index(request):
    # 人気の旅行パッケージを表示（完売も含めて表示）
    popular_packages = TravelPackage.objects.all()[:6]
    
    contexts = {
        'popular_packages': popular_packages,
        'destinations': ['東京', '大阪', '福岡', '沖縄', '北海道', '京都']
    }
    return render(request, "main/index.html", contexts)


# 検索結果ページ
def search_results(request):
    departure = request.GET.get('departure', '')
    destination = request.GET.get('destination', '')
    departure_date = request.GET.get('departure_date', '')
    return_date = request.GET.get('return_date', '')
    people = request.GET.get('people', 1)
    
    # 検索条件に基づいてパッケージを絞り込み（完売も含めて表示）
    packages = TravelPackage.objects.all()
    
    if departure:
        packages = packages.filter(outbound_flight__place_from__icontains=departure)
    if destination:
        packages = packages.filter(outbound_flight__place_to__icontains=destination)
    
    contexts = {
        'packages': packages,
        'search_params': {
            'departure': departure,
            'destination': destination,
            'departure_date': departure_date,
            'return_date': return_date,
            'people': people
        }
    }
    return render(request, "main/search_results.html", contexts)


# 宿泊施設検索ページ
def accommodation_search(request):
    from datetime import datetime
    
    location = request.GET.get('location', '')
    min_rank = request.GET.get('rank', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    amenities = request.GET.getlist('amenities')
    checkin_date = request.GET.get('checkin_date', '')
    checkout_date = request.GET.get('checkout_date', '')
    guests = request.GET.get('guests', '1')
    
    # 日付が指定されていない場合の処理
    if not checkin_date or not checkout_date:
        contexts = {
            'accommodations': [],
            'all_amenities': [],
            'search_params': {
                'location': location,
                'rank': min_rank,
                'min_price': min_price,
                'max_price': max_price,
                'amenities': amenities,
                'checkin_date': checkin_date,
                'checkout_date': checkout_date,
                'guests': guests
            },
            'selected_amenities': amenities,
            'locations': ['東京', '大阪', '沖縄', '札幌', '京都', '福岡'],
            'date_required_message': 'チェックイン日とチェックアウト日を指定してください。',
            'is_paginated': False,
            'total_results': 0
        }
        return render(request, "main/accommodation_search.html", contexts)
    
    accommodations = Accommodations.objects.all()
    
    # 検索フィルタを適用
    if location:
        accommodations = accommodations.filter(
            Q(location__icontains=location) | Q(name__icontains=location)
        )
    if min_rank:
        accommodations = accommodations.filter(rank__gte=min_rank)
    if min_price:
        accommodations = accommodations.filter(price_per_night__gte=min_price)
    if max_price:
        accommodations = accommodations.filter(price_per_night__lte=max_price)
    
    # アメニティでフィルタ
    if amenities:
        for amenity in amenities:
            accommodations = accommodations.filter(amenities__contains=amenity)
    
    # 日付による空き状況をチェック
    try:
        checkin = datetime.strptime(checkin_date, '%Y-%m-%d').date()
        checkout = datetime.strptime(checkout_date, '%Y-%m-%d').date()
        
        # 日付の妥当性チェック
        if checkin >= checkout:
            contexts = {
                'accommodations': [],
                'all_amenities': [],
                'search_params': {
                    'location': location,
                    'rank': min_rank,
                    'min_price': min_price,
                    'max_price': max_price,
                    'amenities': amenities,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'guests': guests
                },
                'selected_amenities': amenities,
                'locations': ['東京', '大阪', '沖縄', '札幌', '京都', '福岡'],
                'date_error_message': 'チェックアウト日はチェックイン日より後の日付を指定してください。',
                'is_paginated': False,
                'total_results': 0
            }
            return render(request, "main/accommodation_search.html", contexts)
        
        # 各宿泊施設の空き状況をチェック
        available_accommodations = []
        for accommodation in accommodations:
            is_available = check_accommodation_availability(accommodation, checkin, checkout, int(guests))
            accommodation.available_for_dates = is_available
            available_accommodations.append(accommodation)
        
        accommodations = available_accommodations
    except ValueError:
        # 日付形式が正しくない場合
        contexts = {
            'accommodations': [],
            'all_amenities': [],
            'search_params': {
                'location': location,
                'rank': min_rank,
                'min_price': min_price,
                'max_price': max_price,
                'amenities': amenities,
                'checkin_date': checkin_date,
                'checkout_date': checkout_date,
                'guests': guests
            },
            'selected_amenities': amenities,
            'locations': ['東京', '大阪', '沖縄', '札幌', '京都', '福岡'],
            'date_error_message': '正しい日付形式で入力してください。',
            'is_paginated': False,
            'total_results': 0
        }
        return render(request, "main/accommodation_search.html", contexts)
    
    # ページネーション
    paginator = Paginator(accommodations, 6)  # 1ページあたり6件表示
    page_number = request.GET.get('page')
    page_accommodations = paginator.get_page(page_number)
    
    # 利用可能なアメニティリストを取得
    all_amenities = set()
    for acc in Accommodations.objects.all():
        if acc.amenities and isinstance(acc.amenities, list):
            all_amenities.update(acc.amenities)
    
    contexts = {
        'accommodations': page_accommodations,
        'all_amenities': sorted(all_amenities),
        'search_params': {
            'location': location,
            'rank': min_rank,
            'min_price': min_price,
            'max_price': max_price,
            'amenities': amenities,
            'checkin_date': checkin_date,
            'checkout_date': checkout_date,
            'guests': guests
        },
        'selected_amenities': amenities,
        'locations': ['東京', '大阪', '沖縄', '札幌', '京都', '福岡'],
        'is_paginated': page_accommodations.has_other_pages(),
        'page_obj': page_accommodations,
        'total_results': len(accommodations)
    }
    return render(request, "main/accommodation_search.html", contexts)


def check_accommodation_availability(accommodation, checkin_date, checkout_date, guests):
    """宿泊施設の指定期間の空き状況をチェック"""
    from datetime import timedelta
    from .models import AccommodationAvailability
    
    current_date = checkin_date
    while current_date < checkout_date:
        try:
            availability = AccommodationAvailability.objects.get(
                accommodation=accommodation,
                date=current_date
            )
            if availability.available_rooms < 1:
                return False
        except AccommodationAvailability.DoesNotExist:
            # 空き状況データがない場合は、デフォルトの総部屋数を使用
            if accommodation.total_rooms < 1:
                return False
        
        current_date += timedelta(days=1)
    
    return True


# 航空券検索ページ
def flight_search(request):
    from datetime import datetime
    
    departure = request.GET.get('departure', '') or request.GET.get('place_from', '')
    destination = request.GET.get('destination', '') or request.GET.get('place_to', '')
    departure_date = request.GET.get('departure_date', '')
    return_date = request.GET.get('return_date', '')
    flight_type = request.GET.get('flight_type', '')
    airline = request.GET.get('airline', '')
    flight_number = request.GET.get('flight_number', '')  # 便名検索を追加
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    passengers = request.GET.get('passengers', '1')
    
    # 往復検索かどうかを判定
    is_round_trip = bool(return_date)
    
    # 往路の検索
    outbound_flights = Air.objects.filter(available_seats__gt=0)
    
    # 往路の検索フィルタを適用
    if departure:
        outbound_flights = outbound_flights.filter(place_from__icontains=departure)
    if destination:
        outbound_flights = outbound_flights.filter(place_to__icontains=destination)
    if flight_number:  # 便名検索を追加
        outbound_flights = outbound_flights.filter(flight_number__icontains=flight_number)
    
    # 復路の検索
    return_flights = []
    if is_round_trip:
        return_flights = Air.objects.filter(available_seats__gt=0)
        # 復路は出発地と目的地が逆
        if departure:
            return_flights = return_flights.filter(place_to__icontains=departure)
        if destination:
            return_flights = return_flights.filter(place_from__icontains=destination)
        if flight_number:  # 復路でも便名検索を追加
            return_flights = return_flights.filter(flight_number__icontains=flight_number)
    
    # 出発日による絞り込み
    if departure_date:
        try:
            outbound_search_date = datetime.strptime(departure_date, '%Y-%m-%d').date()
            outbound_flights = outbound_flights.filter(departure_time__date=outbound_search_date)
            
            # 空き状況をチェック
            available_outbound_flights = []
            for flight in outbound_flights:
                is_available = check_flight_availability(flight, outbound_search_date, int(passengers))
                flight.available_for_date = is_available
                flight.flight_direction = 'outbound'
                available_outbound_flights.append(flight)
            
            outbound_flights = available_outbound_flights
        except ValueError:
            # 日付形式が正しくない場合のエラー処理
            departures = list(Air.objects.values_list('place_from', flat=True).distinct())
            destinations_list = list(Air.objects.values_list('place_to', flat=True).distinct())
            airlines = list(Air.objects.values_list('name', flat=True).distinct())
            flight_numbers = list(Air.objects.values_list('flight_number', flat=True).distinct())  # 便名リストを追加
            
            contexts = {
                'flights': [],
                'return_flights': [],
                'search_params': {
                    'departure': departure,
                    'destination': destination,
                    'departure_date': departure_date,
                    'return_date': return_date,
                    'flight_type': flight_type,
                    'airline': airline,
                    'flight_number': flight_number,  # 便名を追加
                    'min_price': min_price,
                    'max_price': max_price,
                    'passengers': passengers
                },
                'departures': sorted(departures),
                'destinations': sorted(destinations_list),
                'airlines': sorted(airlines),
                'flight_numbers': sorted(flight_numbers),  # 便名リストを追加
                'date_error_message': '正しい日付形式で入力してください。',
                'is_paginated': False,
                'total_results': 0,
                'is_round_trip': is_round_trip
            }
            return render(request, "main/flight_search.html", contexts)
    else:
        # 出発日が指定されていない場合はデフォルトの空席情報を使用
        available_outbound_flights = []
        for flight in outbound_flights:
            flight.available_for_date = flight.available_seats >= int(passengers)
            flight.flight_direction = 'outbound'
            available_outbound_flights.append(flight)
        outbound_flights = available_outbound_flights
    
    # 復路日による絞り込み
    if is_round_trip and return_date:
        try:
            return_search_date = datetime.strptime(return_date, '%Y-%m-%d').date()
            return_flights = return_flights.filter(departure_time__date=return_search_date)
            
            # 復路の空き状況をチェック
            available_return_flights = []
            for flight in return_flights:
                is_available = check_flight_availability(flight, return_search_date, int(passengers))
                flight.available_for_date = is_available
                flight.flight_direction = 'return'
                available_return_flights.append(flight)
            
            return_flights = available_return_flights
        except ValueError:
            return_flights = []
    elif is_round_trip:
        # 復路日が指定されていない場合はデフォルトの空席情報を使用
        available_return_flights = []
        for flight in return_flights:
            flight.available_for_date = flight.available_seats >= int(passengers)
            flight.flight_direction = 'return'
            available_return_flights.append(flight)
        return_flights = available_return_flights
    
    # 共通フィルタを適用
    def apply_common_filters(flights_list):
        filtered_flights = flights_list
        if flight_type:
            filtered_flights = [f for f in filtered_flights if f.flight_type == flight_type]
        if airline:
            filtered_flights = [f for f in filtered_flights if airline.lower() in f.name.lower()]
        if flight_number:  # 便名フィルタを追加
            filtered_flights = [f for f in filtered_flights if flight_number.lower() in f.flight_number.lower()]
        if min_price:
            filtered_flights = [f for f in filtered_flights if f.fee >= int(min_price)]
        if max_price:
            filtered_flights = [f for f in filtered_flights if f.fee <= int(max_price)]
        return filtered_flights
    
    outbound_flights = apply_common_filters(outbound_flights)
    if is_round_trip:
        return_flights = apply_common_filters(return_flights)
    
    # 出発時刻でソート
    outbound_flights = sorted(outbound_flights, key=lambda x: x.departure_time)
    if is_round_trip:
        return_flights = sorted(return_flights, key=lambda x: x.departure_time)
    
    # 片道検索の場合は往路のみを表示、往復検索の場合は両方を表示
    if is_round_trip:
        # 往復検索の場合は両方のフライトリストを提供
        all_flights = outbound_flights
    else:
        # 片道検索の場合は往路のみ
        all_flights = outbound_flights
    
    # ページネーション（往路のみ）
    paginator = Paginator(all_flights, 10)  # 1ページあたり10件表示
    page_number = request.GET.get('page')
    page_flights = paginator.get_page(page_number)
    
    # 選択肢のデータを作成
    departures_list = list(Air.objects.values_list('place_from', flat=True).distinct())
    destinations_list = list(Air.objects.values_list('place_to', flat=True).distinct())
    airlines = list(Air.objects.values_list('name', flat=True).distinct())
    flight_numbers = list(Air.objects.values_list('flight_number', flat=True).distinct())  # 便名リストを追加
    
    contexts = {
        'flights': page_flights,
        'return_flights': return_flights if is_round_trip else [],
        'search_params': {
            'departure': departure,
            'destination': destination,
            'departure_date': departure_date,
            'return_date': return_date,
            'flight_type': flight_type,
            'airline': airline,
            'flight_number': flight_number,  # 便名を追加
            'min_price': min_price,
            'max_price': max_price,
            'passengers': passengers
        },
        'departures': sorted(departures_list),
        'destinations': sorted(destinations_list),
        'airlines': sorted(airlines),
        'flight_numbers': sorted(flight_numbers),  # 便名リストを追加
        'is_paginated': page_flights.has_other_pages(),
        'page_obj': page_flights,
        'total_results': len(all_flights),
        'is_round_trip': is_round_trip,
        'outbound_count': len(outbound_flights),
        'return_count': len(return_flights) if is_round_trip else 0
    }
    
    # モーダル表示用の場合はパーシャルテンプレートを返す
    if request.GET.get('modal') == 'true':
        contexts['flight_list'] = page_flights  # パーシャルテンプレート用
        contexts['flight_direction'] = 'oneway'  # デフォルトで片道
        return render(request, "main/flight_list_partial.html", contexts)
    
    return render(request, "main/flight_search.html", contexts)


def check_flight_availability(flight, departure_date, passengers):
    """航空券の指定日時の空き状況をチェック"""
    from .models import FlightAvailability
    
    try:
        availability = FlightAvailability.objects.get(
            flight=flight,
            date=departure_date
        )
        return availability.available_seats >= passengers
    except FlightAvailability.DoesNotExist:
        # 空き状況データがない場合は、デフォルトの空席数を使用
        return flight.available_seats >= passengers


# 予約作成ページ
# AIエージェント比較ページ
def ai_comparison(request):
    contexts = {
        'systems': [
            {
                'id': 'ai_agent',
                'name': 'AIエージェント',
                'description': 'OpenAI APIを使用した高度な会話型AI',
                'features': ['自然言語理解', '文脈把握', '推論能力', '柔軟な対応']
            },
            {
                'id': 'ai_assistant',
                'name': 'AIアシスタント',
                'description': 'タスク特化型のAIアシスタント',
                'features': ['定型業務', '効率的処理', 'データ検索', '予約支援']
            },
            {
                'id': 'rule_bot',
                'name': 'ルールベースBot',
                'description': '事前定義ルールに基づく応答システム',
                'features': ['確実な応答', '高速処理', 'キーワード検出', 'FAQ対応']
            }
        ]
    }
    return render(request, "main/ai_comparison.html", contexts)


# チャットインターフェース
def chat_interface(request, system_type):
    if system_type not in ['ai_agent', 'ai_assistant', 'rule_bot']:
        return render(request, "main/error.html", {'error': 'Invalid system type'})
    
    # 新しいセッションを作成
    session_id = str(uuid.uuid4())
    ChatSession.objects.create(
        session_id=session_id,
        session_type=system_type
    )
    
    contexts = {
        'session_id': session_id,
        'system_type': system_type,
        'system_name': {
            'ai_agent': 'AIエージェント',
            'ai_assistant': 'AIアシスタント', 
            'rule_bot': 'ルールベースBot'
        }.get(system_type, system_type)
    }
    return render(request, "main/chat_interface.html", contexts)


# チャットメッセージ処理API
@csrf_exempt
def chat_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        message = data.get('message')
        
        session = get_object_or_404(ChatSession, session_id=session_id)
        
        # ユーザーメッセージを記録
        ChatMessage.objects.create(
            session=session,
            message_type='user',
            content=message
        )
        
        def _generate_and_persist():
            start_time = time.time()
            try:
                if session.session_type == 'ai_agent':
                    response = handle_ai_agent(message, session)
                elif session.session_type == 'ai_assistant':
                    response = handle_ai_assistant(message, session)
                elif session.session_type == 'rule_bot':
                    response = handle_rule_bot(message, session)
                else:
                    response = {'content': 'システムエラーが発生しました。', 'intent': 'error', 'confidence': 0.0}
            except Exception as e:
                response = {
                    'content': f'内部エラーが発生しました: {str(e)}',
                    'intent': 'error',
                    'confidence': 0.0,
                    'reasoning': {'error': str(e)}
                }
            processing_time = time.time() - start_time
            try:
                ChatMessage.objects.create(
                    session=session,
                    message_type=session.session_type,
                    content=response['content'],
                    reasoning_process=response.get('reasoning', {})
                )
                SystemResponse.objects.create(
                    session=session,
                    intent_detected=response.get('intent', ''),
                    confidence_score=response.get('confidence', None),
                    processing_time=processing_time,
                    response_generated=response['content']
                )
            except Exception:
                # 永続化の失敗はレスポンス生成を妨げない
                pass
            # 呼び出し側へ返すデータ
            return {
                'response': response['content'],
                'intent': response.get('intent', ''),
                'processing_time': processing_time,
                'confidence': response.get('confidence')
            }

        # バックグラウンドで実行しつつ、一定時間でタイムアウトしたら即時応答
        future = _agent_executor.submit(_generate_and_persist)
        try:
            result = future.result(timeout=AGENT_SYNC_TIMEOUT)
            return JsonResponse(result)
        except FuturesTimeoutError:
            # タイムアウト時はバックグラウンドに継続させ、即時のプレースホルダーを返す
            return JsonResponse({
                'response': 'ただいま回答を作成中です。数十秒後に自動で更新されます。',
                'intent': 'processing',
                'processing_time': AGENT_SYNC_TIMEOUT,
                'processing': True
            })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# 会話履歴管理API
@csrf_exempt
def get_conversation_history(request):
    """会話履歴を取得するAPI"""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
    
    try:
        session_id = request.GET.get('session_id')
        if not session_id:
            return JsonResponse({'error': 'session_id is required'}, status=400)
        
        # セッションが存在するかチェック
        session = get_object_or_404(ChatSession, session_id=session_id)
        
        # TravelChatAssistantのインスタンスから履歴を取得
        session_id_str = str(session_id)
        if session_id_str in session_assistants:
            assistant = session_assistants[session_id_str]
            history = assistant.get_conversation_history()
            
            return JsonResponse({
                'conversation_history': history,
                'total_messages': len(history),
                'session_id': session_id
            })
        else:
            return JsonResponse({
                'conversation_history': [],
                'total_messages': 0,
                'session_id': session_id,
                'message': 'No conversation history found for this session'
            })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def clear_conversation_history(request):
    """会話履歴をクリアするAPI"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        if not session_id:
            return JsonResponse({'error': 'session_id is required'}, status=400)
        
        # セッションが存在するかチェック
        session = get_object_or_404(ChatSession, session_id=session_id)
        
        # TravelChatAssistantのインスタンスの履歴をクリア
        session_id_str = str(session_id)
        if session_id_str in session_assistants:
            assistant = session_assistants[session_id_str]
            assistant.clear_history()
            
            return JsonResponse({
                'message': 'Conversation history cleared successfully',
                'session_id': session_id
            })
        else:
            return JsonResponse({
                'message': 'No conversation history found for this session',
                'session_id': session_id
            })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# AI応答処理関数群
def handle_ai_agent(message, session):
    """AIエージェント（TravelAgentSystem使用）の応答処理"""
    import asyncio
    session_id = str(session.session_id)
    
    try:
        # 非同期処理を同期環境で実行するためのヘルパー関数
        def run_agent_sync():
            try:
                # 新しいイベントループを作成して実行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # TravelAgentSystemのインスタンスを作成（セッションIDで管理）
                    agent_system = TravelAgentSystem(
                        session_id=f"bookiniad_chat_{session_id}",
                        db_path="./agents_conversation.db"
                    )
                    
                    # ベースエージェントで応答を生成
                    response_content = agent_system.chat(message, "base_agent")
                    return response_content
                    
                finally:
                    loop.close()
                    
            except Exception:
                # TravelAgentSystemでエラーが発生した場合、フォールバックとしてTravelChatAssistantを使用
                from main.agents.assistant import TravelChatAssistant
                fallback_assistant = TravelChatAssistant()
                return fallback_assistant.chat(message)
        
        # 同期的に非同期処理を実行
        response_content = run_agent_sync()
        
        # 意図検出（メッセージ内容に基づく分類）
        intent = 'general'
        confidence = 0.8
        
        if any(word in message.lower() for word in ['航空券', 'フライト', '飛行機', 'air', '便']):
            intent = 'flight_search'
            confidence = 0.9
        elif any(word in message.lower() for word in ['ホテル', '宿泊', '泊まり', 'hotel', 'accommodation', '宿']):
            intent = 'accommodation_search'
            confidence = 0.9
        elif any(word in message.lower() for word in ['予約', 'booking', '予約番号', '照会']):
            intent = 'booking_inquiry'
            confidence = 0.9
        elif any(word in message.lower() for word in ['推奨', 'おすすめ', 'recommend', '旅行', 'travel']):
            intent = 'travel_recommendation'
            confidence = 0.8
        elif any(word in message.lower() for word in ['こんにちは', 'hello', 'はじめまして', 'こんばんは']):
            intent = 'greeting'
            confidence = 0.95
        elif any(word in message.lower() for word in ['ありがとう', 'thank', 'thanks', 'すみません']):
            intent = 'courtesy'
            confidence = 0.9
        
        return {
            'content': response_content,
            'intent': intent,
            'confidence': confidence,
            'reasoning': {
                'model': 'TravelAgentSystem (Multi-Agent)',
                'session_id': session_id,
                'agent_system': 'base_agent',
                'db_path': './agents_conversation.db',
                'execution_mode': 'sync_wrapper'
            }
        }
        
    except Exception as e:
        # エラーが発生した場合のフォールバック（TravelChatAssistantを使用）
        try:
            from main.agents.assistant import TravelChatAssistant
            fallback_assistant = TravelChatAssistant()
            fallback_response = fallback_assistant.chat(message)
            
            return {
                'content': fallback_response,
                'intent': 'general',
                'confidence': 0.7,
                'reasoning': {
                    'error': str(e),
                    'fallback': True,
                    'system': 'TravelChatAssistant (fallback)',
                    'original_system': 'TravelAgentSystem'
                }
            }
        except Exception as fallback_error:
            # 最終的なフォールバック
            return {
                'content': '申し訳ございません。システムにエラーが発生しました。しばらくしてから再度お試しください。',
                'intent': 'error',
                'confidence': 1.0,
                'reasoning': {
                    'error': str(e),
                    'fallback_error': str(fallback_error),
                    'system': 'manual_fallback'
                }
            }


def handle_ai_assistant(message, session):
    """AIアシスタント（OpenAI Chat Completions API使用）の応答処理"""
    session_id = str(session.session_id)
    
    # セッションごとのTravelChatAssistantインスタンスを取得または作成
    if session_id not in session_assistants:
        session_assistants[session_id] = TravelChatAssistant()
    
    assistant = session_assistants[session_id]
    
    try:
        # TravelChatAssistantで応答を生成
        response_content = assistant.chat(message)
        
        # 意図検出（簡単な分類）
        intent = 'general'
        confidence = 0.8
        
        if any(word in message.lower() for word in ['航空券', 'フライト', '飛行機', 'air']):
            intent = 'flight_search'
        elif any(word in message.lower() for word in ['ホテル', '宿泊', '泊まり', 'hotel', 'accommodation']):
            intent = 'accommodation_search'
        elif any(word in message.lower() for word in ['推奨', 'おすすめ', 'recommend']):
            intent = 'travel_recommendation'
        elif any(word in message.lower() for word in ['こんにちは', 'hello', 'はじめまして']):
            intent = 'greeting'
            confidence = 0.9
        
        return {
            'content': response_content,
            'intent': intent,
            'confidence': confidence,
            'reasoning': {
                'model': 'OpenAI GPT-4o-mini',
                'session_id': session_id,
                'conversation_length': len(assistant.get_conversation_history())
            }
        }
        
    except Exception as e:
        # エラーが発生した場合のフォールバック
        return {
            'content': f'申し訳ございません。システムにエラーが発生しました。再度お試しください。（エラー: {str(e)}）',
            'intent': 'error',
            'confidence': 1.0,
            'reasoning': {
                'error': str(e),
                'fallback': True
            }
        }


def detect_intent_advanced(message):
    """高度な意図検出（実際の実装ではNLPライブラリやAPIを使用）"""
    # シンプルな実装例
    intents = []
    if any(word in message for word in ['検索', '探す', 'search', '探して']):
        intents.append('search')
    if any(word in message for word in ['予約', 'booking', '申し込み']):
        intents.append('booking')
    if any(word in message for word in ['こんにちは', 'hello', 'はじめまして']):
        intents.append('greeting')
    return intents


# 予約照会ページ
def booking_inquiry(request):
    """予約照会機能"""
    booking = None
    error_message = None
    booking_details = None
    
    if request.method == 'POST':
        reservation_number = request.POST.get('reservation_number', '').strip()
        
        if not reservation_number:
            error_message = '予約番号を入力してください。'
        else:
            try:
                # UUID形式の文字列を適切に処理
                import uuid
                try:
                    # 文字列をUUIDオブジェクトに変換して検証
                    uuid_obj = uuid.UUID(reservation_number)
                    booking = Booking.objects.get(reservation_number=uuid_obj)
                except ValueError:
                    # UUID形式でない場合は、文字列として検索を試行
                    booking = Booking.objects.get(reservation_number=reservation_number)
                
                # チェックインまでの日数を計算
                from datetime import date, datetime
                checkin_date = None
                checkout_date = None
                
                if booking.from_date:
                    # 日付型に統一して変換
                    if isinstance(booking.from_date, datetime):
                        checkin_date = booking.from_date.date()
                    elif isinstance(booking.from_date, date):
                        checkin_date = booking.from_date
                    else:
                        # 文字列の場合の処理
                        try:
                            checkin_date = datetime.strptime(str(booking.from_date), '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            checkin_date = date.today()
                    
                    days_until_checkin = (checkin_date - date.today()).days
                else:
                    days_until_checkin = 0
                
                # 宿泊日数を計算
                if booking.from_date and booking.to_date:
                    if isinstance(booking.to_date, datetime):
                        checkout_date = booking.to_date.date()
                    elif isinstance(booking.to_date, date):
                        checkout_date = booking.to_date
                    else:
                        try:
                            checkout_date = datetime.strptime(str(booking.to_date), '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            checkout_date = date.today()
                    
                    if checkin_date and checkout_date:
                        nights = (checkout_date - checkin_date).days
                    else:
                        nights = 1
                else:
                    nights = 1
                
                # 航空券情報を取得
                flights = booking.air.all()
                
                # 価格の内訳を計算
                accommodation_total = 0
                flight_total = 0
                
                if booking.accommodations:
                    accommodation_total = booking.accommodations.price_per_night * nights * booking.num_of_people
                
                for flight in flights:
                    flight_total += flight.fee * booking.num_of_people
                
                # 正しい合計金額を計算
                calculated_total = accommodation_total + flight_total
                
                # 予約詳細情報を辞書として作成
                booking_details = {
                    'nights': nights,
                    'days_until_checkin': max(0, days_until_checkin),
                    'accommodation_total': accommodation_total,
                    'flight_total': flight_total,
                    'calculated_total': calculated_total,  # 人数を反映した正しい合計金額
                    'flights': flights,
                    'checkin_date': checkin_date if booking.from_date else None,
                    'checkout_date': checkout_date if booking.to_date else None,
                }
                
            except Booking.DoesNotExist:
                error_message = f'予約番号「{reservation_number}」が見つかりません。正しい予約番号を入力してください。'
                booking = None
    
    contexts = {
        'booking': booking,
        'booking_details': booking_details,
        'error_message': error_message
    }
    return render(request, "main/booking_inquiry.html", contexts)


# パフォーマンス分析ページ
def performance_analysis(request):
    # 各システムのパフォーマンスデータを集計
    performance_data = {}
    
    for system_type in ['ai_agent', 'ai_assistant', 'rule_bot']:
        sessions = ChatSession.objects.filter(session_type=system_type)
        responses = SystemResponse.objects.filter(session__session_type=system_type)
        
        if responses.exists():
            avg_response_time = responses.aggregate(avg_time=models.Avg('processing_time'))['avg_time']
            total_sessions = sessions.count()
            
            performance_data[system_type] = {
                'avg_response_time': round(avg_response_time or 0, 3),
                'total_sessions': total_sessions,
                'system_name': {
                    'ai_agent': 'AIエージェント',
                    'ai_assistant': 'AIアシスタント',
                    'rule_bot': 'ルールベースBot'
                }.get(system_type)
            }
    
    contexts = {
        'performance_data': performance_data
    }
    return render(request, "main/performance_analysis.html", contexts)


# カート機能のヘルパー関数
def get_or_create_cart(request):
    """セッションのカートを取得または作成"""
    session_id = request.session.session_key
    if not session_id:
        request.session.create()
        session_id = request.session.session_key
    
    cart, created = Cart.objects.get_or_create(session_id=session_id)
    return cart


# カートページ
def cart(request):
    """カート内容を表示"""
    cart_obj = get_or_create_cart(request)
    cart_items = cart_obj.items.all().order_by('-added_at')
    
    # 航空券と宿泊施設の料金を分けて計算
    flight_total = 0
    accommodation_total = 0
    
    for item in cart_items:
        if item.item_type == 'flight':
            flight_total += item.get_total_price()
        elif item.item_type == 'accommodation':
            accommodation_total += item.get_total_price()
    
    contexts = {
        'cart': cart_obj,
        'cart_items': cart_items,
        'total_price': cart_obj.get_total_price(),
        'flight_count': cart_obj.get_flight_count(),
        'accommodation_count': cart_obj.get_accommodation_count(),
        'flight_total': flight_total,
        'accommodation_total': accommodation_total
    }
    return render(request, "main/cart.html", contexts)


# カートに航空券を追加
@csrf_exempt
def add_flight_to_cart(request):
    """航空券をカートに追加"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        flight_id = data.get('flight_id')
        direction = data.get('direction', 'oneway')  # oneway, outbound, return
        
        flight = get_object_or_404(Air, id=flight_id)
        cart_obj = get_or_create_cart(request)
        
        # 同じ航空券が既にカートにあるかチェック
        existing_item = cart_obj.items.filter(
            item_type='flight',
            flight=flight,
            flight_direction=direction
        ).first()
        
        if existing_item:
            return JsonResponse({
                'error': 'この航空券は既にカートに追加されています',
                'cart_count': cart_obj.items.count()
            }, status=400)
        
        # カートに追加
        CartItem.objects.create(
            cart=cart_obj,
            item_type='flight',
            flight=flight,
            flight_direction=direction,
            unit_price=flight.fee,
            quantity=1
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{flight.name} ({direction}) をカートに追加しました',
            'cart_count': cart_obj.items.count(),
            'total_price': cart_obj.get_total_price()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# カートに宿泊施設を追加
@csrf_exempt
def add_accommodation_to_cart(request):
    """宿泊施設をカートに追加"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        accommodation_id = data.get('accommodation_id')
        checkin_date = data.get('checkin_date')
        checkout_date = data.get('checkout_date')
        
        if not checkin_date or not checkout_date:
            return JsonResponse({'error': 'チェックイン日とチェックアウト日が必要です'}, status=400)
        
        accommodation = get_object_or_404(Accommodations, id=accommodation_id)
        cart_obj = get_or_create_cart(request)
        
        from datetime import datetime
        checkin = datetime.strptime(checkin_date, '%Y-%m-%d').date()
        checkout = datetime.strptime(checkout_date, '%Y-%m-%d').date()
        
        if checkout <= checkin:
            return JsonResponse({'error': 'チェックアウト日はチェックイン日より後にしてください'}, status=400)
        
        # 同じ宿泊施設・期間が既にカートにあるかチェック
        existing_item = cart_obj.items.filter(
            item_type='accommodation',
            accommodation=accommodation,
            check_in_date=checkin,
            check_out_date=checkout
        ).first()
        
        if existing_item:
            return JsonResponse({
                'error': 'この宿泊施設・期間は既にカートに追加されています',
                'cart_count': cart_obj.items.count()
            }, status=400)
        
        # カートに追加
        CartItem.objects.create(
            cart=cart_obj,
            item_type='accommodation',
            accommodation=accommodation,
            check_in_date=checkin,
            check_out_date=checkout,
            unit_price=accommodation.price_per_night,
            quantity=1
        )
        
        nights = (checkout - checkin).days
        return JsonResponse({
            'success': True,
            'message': f'{accommodation.name} ({nights}泊) をカートに追加しました',
            'cart_count': cart_obj.items.count(),
            'total_price': cart_obj.get_total_price(),
            'accommodation': {
                'id': accommodation.id,
                'name': accommodation.name,
                'location': accommodation.location,
                'price_per_night': accommodation.price_per_night
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# カートからアイテムを削除
@csrf_exempt
def remove_from_cart(request):
    """カートからアイテムを削除"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        
        cart_obj = get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart_obj)
        
        item_name = str(item)
        item.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{item_name} をカートから削除しました',
            'cart_count': cart_obj.items.count(),
            'total_price': cart_obj.get_total_price()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# カートをクリア
@csrf_exempt
def clear_cart(request):
    """カートを空にする"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        cart_obj = get_or_create_cart(request)
        cart_obj.items.all().delete()
        
        return JsonResponse({
            'success': True,
            'message': 'カートを空にしました',
            'cart_count': 0,
            'total_price': 0
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# カートから予約作成
def create_booking_from_cart(request):
    """カートの内容から予約を作成"""
    if request.method == 'POST':
        cart_obj = get_or_create_cart(request)
        cart_items = cart_obj.items.all()
        
        if not cart_items.exists():
            return JsonResponse({
                'success': False,
                'error': 'カートが空です'
            })
        
        # 予約データを準備
        customer_name = request.POST.get('customer_name', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        guests = int(request.POST.get('guests', 1))
        special_requests = request.POST.get('special_requests', '').strip()
        
        # 人数を反映した合計金額を計算
        total_price = 0
        for item in cart_items:
            if item.item_type == 'flight' and item.flight:
                # 航空券：人数分の料金
                total_price += item.flight.fee * guests
            elif item.item_type == 'accommodation' and item.accommodation:
                # 宿泊施設：1泊料金 × 宿泊日数 × 人数
                nights = item.get_nights() if item.get_nights() > 0 else 1
                total_price += item.accommodation.price_per_night * nights * guests
            elif item.item_type == 'package' and item.package:
                # パッケージ：パッケージ料金 × 人数
                total_price += item.package.total_price * guests
        
        if not customer_name:
            return JsonResponse({
                'success': False,
                'error': 'お名前を入力してください'
            })
        
        if not customer_email:
            return JsonResponse({
                'success': False,
                'error': 'メールアドレスを入力してください'
            })
        
        # 予約期間の決定（カート内の最初と最後の日付を使用）
        from_date = None
        to_date = None
        accommodation = None
        place = ''
        
        # 宿泊施設からの日付を取得
        for item in cart_items:
            if item.item_type == 'accommodation' and item.check_in_date and item.check_out_date:
                if from_date is None or item.check_in_date < from_date:
                    from_date = item.check_in_date
                if to_date is None or item.check_out_date > to_date:
                    to_date = item.check_out_date
                accommodation = item.accommodation
                place = item.accommodation.location
        
        # 航空券からの日付を取得（宿泊日程がない場合）
        if from_date is None:
            for item in cart_items:
                if item.item_type == 'flight' and item.flight:
                    flight_date = item.flight.departure_time
                    if from_date is None or flight_date < from_date:
                        from_date = flight_date
                    if to_date is None or flight_date > to_date:
                        to_date = flight_date
                    if not place:
                        place = item.flight.place_to
        
        # 日付が取得できない場合は今日の日付を使用
        if from_date is None:
            from datetime import datetime
            from_date = datetime.now()
            to_date = from_date
        
        # DateTimeFieldに対応するため、日付のみの場合は時刻を追加
        if hasattr(from_date, 'date'):
            # 既にdatetimeの場合はそのまま
            pass
        else:
            # dateの場合はdatetimeに変換
            from datetime import datetime, time
            if from_date:
                from_date = datetime.combine(from_date, time(14, 0))  # 14:00
            if to_date:
                to_date = datetime.combine(to_date, time(11, 0))     # 11:00
        
        if not place:
            place = '未指定'
        
        try:
            # 宿泊施設がない場合はダミーの宿泊施設を作成するか、最初のものを使用
            if not accommodation:
                # 航空券のみの場合、最初の宿泊施設を使用（必須フィールドのため）
                accommodation = Accommodations.objects.first()
                if not accommodation:
                    return JsonResponse({
                        'success': False,
                        'error': '予約作成に必要な宿泊施設情報が見つかりません'
                    })
            
            # Bookingモデルのフィールド名に合わせて予約を作成
            booking = Booking.objects.create(
                from_date=from_date,
                to_date=to_date,
                num_of_people=guests,
                total_fee=total_price,  # 人数を反映した正しい合計金額
                place=place,
                accommodations=accommodation
            )
            
            # 航空券を追加
            flights_list = []
            for item in cart_items:
                if item.item_type == 'flight' and item.flight:
                    booking.air.add(item.flight)
                    flights_list.append({
                        'id': item.flight.pk,
                        'airline': item.flight.name,
                        'departure': item.flight.place_from,
                        'destination': item.flight.place_to,
                        'departure_time': item.flight.departure_time.strftime('%H:%M') if item.flight.departure_time else '',
                        'price': item.flight.fee
                    })
            
            # 宿泊施設情報
            accommodations_list = []
            if accommodation:
                accommodations_list.append({
                    'id': accommodation.pk,
                    'name': accommodation.name,
                    'location': accommodation.location,
                    'price': accommodation.price_per_night
                })
            
            # カートをクリア
            cart_items.delete()
            
            return JsonResponse({
                'success': True,
                'booking': {
                    'id': booking.pk,
                    'reservation_number': str(booking.reservation_number),
                    'customer_name': customer_name,
                    'customer_email': customer_email,
                    'customer_phone': customer_phone,
                    'num_of_people': booking.num_of_people,
                    'from_date': booking.from_date.isoformat() if booking.from_date else None,
                    'to_date': booking.to_date.isoformat() if booking.to_date else None,
                    'total_fee': booking.total_fee,
                    'special_requests': special_requests,
                    'created_at': booking.from_date.isoformat() if booking.from_date else None,  # created_atフィールドがないので代替
                    'accommodations': accommodations_list,
                    'flights': flights_list
                },
                'message': '予約が完了しました'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'予約作成中にエラーが発生しました: {str(e)}'
            })
    
    # GET リクエストの場合は予約フォームを表示
    cart_obj = get_or_create_cart(request)
    cart_items = cart_obj.items.all()
    
    if not cart_items.exists():
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.warning(request, 'カートが空です。航空券や宿泊施設を追加してください。')
        return redirect('cart')
    
    contexts = {
        'cart': cart_obj,
        'cart_items': cart_items,
        'total_price': cart_obj.get_total_price()
    }
    return render(request, "main/booking_form.html", contexts)


# 予約完了画面
def booking_complete(request):
    """予約完了画面を表示"""
    return render(request, "main/booking_complete.html")
