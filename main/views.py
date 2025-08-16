from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.core.paginator import Paginator
from django.db.models import Q
import json
import uuid
import time

from .models import (
    Accommodations, Air, Booking, TravelPackage,
    ChatSession, ChatMessage,
    SystemResponse
)


# トップページ
def index(request):
    # 人気の旅行パッケージを表示
    popular_packages = TravelPackage.objects.filter(is_available=True)[:6]
    
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
    
    # 検索条件に基づいてパッケージを絞り込み
    packages = TravelPackage.objects.filter(is_available=True)
    
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
            'date_required_message': 'チェックイン日とチェックアウト日を指定してください。'
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
                'date_error_message': 'チェックアウト日はチェックイン日より後の日付を指定してください。'
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
            'date_error_message': '正しい日付形式で入力してください。'
        }
        return render(request, "main/accommodation_search.html", contexts)
    
    # ページネーション
    paginator = Paginator(accommodations, 6)
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
        'locations': ['東京', '大阪', '沖縄', '札幌', '京都', '福岡']
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
    flight_type = request.GET.get('flight_type', '')
    airline = request.GET.get('airline', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    passengers = request.GET.get('passengers', '1')
    
    # 出発日が指定されていない場合の処理
    if not departure_date:
        # 選択肢のデータを作成
        departures = list(Air.objects.values_list('place_from', flat=True).distinct())
        destinations = list(Air.objects.values_list('place_to', flat=True).distinct())
        airlines = list(Air.objects.values_list('name', flat=True).distinct())
        
        contexts = {
            'flights': [],
            'search_params': {
                'departure': departure,
                'destination': destination,
                'departure_date': departure_date,
                'flight_type': flight_type,
                'airline': airline,
                'min_price': min_price,
                'max_price': max_price,
                'passengers': passengers
            },
            'departures': sorted(departures),
            'destinations': sorted(destinations),
            'airlines': sorted(airlines),
            'date_required_message': '出発日を指定してください。'
        }
        return render(request, "main/flight_search.html", contexts)
    
    flights = Air.objects.filter(available_seats__gt=0)
    
    # 検索フィルタを適用
    if departure:
        flights = flights.filter(place_from__icontains=departure)
    if destination:
        flights = flights.filter(place_to__icontains=destination)
    
    try:
        search_date = datetime.strptime(departure_date, '%Y-%m-%d').date()
        flights = flights.filter(departure_time__date=search_date)
        
        # 空き状況をチェック
        available_flights = []
        for flight in flights:
            is_available = check_flight_availability(flight, search_date, int(passengers))
            flight.available_for_date = is_available
            available_flights.append(flight)
        
        flights = available_flights
    except ValueError:
        # 日付形式が正しくない場合
        departures = list(Air.objects.values_list('place_from', flat=True).distinct())
        destinations = list(Air.objects.values_list('place_to', flat=True).distinct())
        airlines = list(Air.objects.values_list('name', flat=True).distinct())
        
        contexts = {
            'flights': [],
            'search_params': {
                'departure': departure,
                'destination': destination,
                'departure_date': departure_date,
                'flight_type': flight_type,
                'airline': airline,
                'min_price': min_price,
                'max_price': max_price,
                'passengers': passengers
            },
            'departures': sorted(departures),
            'destinations': sorted(destinations),
            'airlines': sorted(airlines),
            'date_error_message': '正しい日付形式で入力してください。'
        }
        return render(request, "main/flight_search.html", contexts)
            
    if flight_type:
        flights = [f for f in flights if f.flight_type == flight_type]
    if airline:
        flights = [f for f in flights if airline.lower() in f.name.lower()]
    if min_price:
        flights = [f for f in flights if f.fee >= int(min_price)]
    if max_price:
        flights = [f for f in flights if f.fee <= int(max_price)]
    
    # 出発時刻でソート
    flights = sorted(flights, key=lambda x: x.departure_time)
    
    # ページネーション
    paginator = Paginator(flights, 10)
    page_number = request.GET.get('page')
    page_flights = paginator.get_page(page_number)
    
    # 選択肢のデータを作成
    departures = list(Air.objects.values_list('place_from', flat=True).distinct())
    destinations = list(Air.objects.values_list('place_to', flat=True).distinct())
    airlines = list(Air.objects.values_list('name', flat=True).distinct())
    
    contexts = {
        'flights': page_flights,
        'search_params': {
            'departure': departure,
            'destination': destination,
            'departure_date': departure_date,
            'flight_type': flight_type,
            'airline': airline,
            'min_price': min_price,
            'max_price': max_price,
            'passengers': passengers
        },
        'departures': sorted(departures),
        'destinations': sorted(destinations),
        'airlines': sorted(airlines)
    }
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
def create_booking(request):
    if request.method == 'POST':
        # フォームからのデータを取得
        accommodation_id = request.POST.get('accommodation_id')
        flight_id = request.POST.get('flight_id')
        customer_name = request.POST.get('customer_name')
        customer_email = request.POST.get('customer_email')
        customer_phone = request.POST.get('customer_phone')
        check_in_date = request.POST.get('check_in_date')
        check_out_date = request.POST.get('check_out_date')
        guests = int(request.POST.get('guests', 1))
        special_requests = request.POST.get('special_requests', '')
        
        # 日付の計算
        from datetime import datetime, date
        if check_in_date and check_out_date:
            checkin = datetime.strptime(check_in_date, '%Y-%m-%d').date()
            checkout = datetime.strptime(check_out_date, '%Y-%m-%d').date()
            nights = (checkout - checkin).days
        else:
            nights = 1
            checkin = date.today()
            checkout = date.today()
        
        # 関連オブジェクトを取得
        accommodation = None
        outbound_flight = None
        total_price = 0
        accommodation_total = 0
        
        if accommodation_id:
            accommodation = get_object_or_404(Accommodations, id=accommodation_id)
            accommodation_total = accommodation.price_per_night * nights
            total_price += accommodation_total
            
        if flight_id:
            outbound_flight = get_object_or_404(Air, id=flight_id)
            total_price += outbound_flight.fee
        
        # 予約を作成
        booking = Booking.objects.create(
            accommodations=accommodation,
            num_of_people=guests,
            total_fee=total_price,
            place=accommodation.location if accommodation else '',
            from_date=checkin,
            to_date=checkout
        )
        
        # 航空券を関連付け
        if outbound_flight:
            booking.air.add(outbound_flight)
        
        # 予約完了ページにリダイレクト用のデータを作成
        booking_data = {
            'id': booking.reservation_number,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'check_in_date': checkin,
            'check_out_date': checkout,
            'guests': guests,
            'special_requests': special_requests,
            'accommodation': accommodation,
            'outbound_flight': outbound_flight,
            'total_price': total_price,
            'accommodation_total': accommodation_total,
            'nights': nights,
            'created_at': datetime.now()
        }
        
        # チェックインまでの日数を計算
        days_until_checkin = (checkin - date.today()).days
        
        return render(request, "main/booking_success.html", {
            'booking': type('obj', (object,), booking_data),
            'days_until_checkin': max(0, days_until_checkin)
        })
    
    # GETリクエストの場合は予約フォームを表示
    return render(request, "main/create_booking.html")


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
    chat_session = ChatSession.objects.create(
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
        user_message = ChatMessage.objects.create(
            session=session,
            message_type='user',
            content=message
        )
        
        # システムタイプに応じて応答を生成
        start_time = time.time()
        
        if session.session_type == 'ai_agent':
            response = handle_ai_agent(message, session)
        elif session.session_type == 'ai_assistant':
            response = handle_ai_assistant(message, session)
        elif session.session_type == 'rule_bot':
            response = handle_rule_bot(message, session)
        else:
            response = {'content': 'システムエラーが発生しました。', 'intent': 'error'}
        
        processing_time = time.time() - start_time
        
        # システム応答を記録
        system_message = ChatMessage.objects.create(
            session=session,
            message_type=session.session_type,
            content=response['content'],
            reasoning_process=response.get('reasoning', {})
        )
        
        # パフォーマンス記録
        SystemResponse.objects.create(
            session=session,
            intent_detected=response.get('intent', ''),
            confidence_score=response.get('confidence', None),
            processing_time=processing_time,
            response_generated=response['content']
        )
        
        return JsonResponse({
            'response': response['content'],
            'intent': response.get('intent', ''),
            'processing_time': processing_time
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# AI応答処理関数群
def handle_ai_agent(message, session):
    """AIエージェント（高度なAI）の応答処理"""
    # 実際の実装ではOpenAI APIを呼び出す
    intents = detect_intent_advanced(message)
    
    if 'search' in intents or '検索' in message or '探して' in message:
        return {
            'content': f'検索のお手伝いをします。どちらへご旅行をお考えでしょうか？\n具体的な条件（出発地、目的地、日程、人数、予算など）を教えてください。',
            'intent': 'search_assistance',
            'confidence': 0.9,
            'reasoning': {'detected_keywords': ['検索', '探して'], 'context_analysis': 'travel_search'}
        }
    elif '予約' in message or 'booking' in message.lower():
        return {
            'content': '予約の手続きをサポートします。まず、ご希望の旅行プランを検索して、お気に入りのパッケージを見つけましょう。',
            'intent': 'booking_assistance',
            'confidence': 0.85,
            'reasoning': {'intent_classification': 'booking', 'next_action': 'search_packages'}
        }
    else:
        return {
            'content': 'bookiniad.comへようこそ！航空券と宿泊施設をセットでお得に予約できます。\nどのようなご旅行をお探しでしょうか？',
            'intent': 'greeting',
            'confidence': 0.7,
            'reasoning': {'fallback_response': True}
        }


def handle_ai_assistant(message, session):
    """AIアシスタント（タスク特化型）の応答処理"""
    # シンプルな意図検出
    if any(word in message for word in ['検索', '探す', 'search']):
        packages = TravelPackage.objects.filter(is_available=True)[:3]
        package_list = "\n".join([f"• {pkg.name} - ¥{pkg.total_price:,}" for pkg in packages])
        
        return {
            'content': f'現在利用可能なお勧めパッケージです：\n{package_list}\n\n詳細な検索をご希望でしたら、条件を教えてください。',
            'intent': 'package_recommendation',
            'confidence': 0.8
        }
    elif any(word in message for word in ['予約', 'booking']):
        return {
            'content': '予約をご希望ですね。まずはパッケージをお選びください。検索画面でご希望の条件を入力していただけます。',
            'intent': 'booking_guidance',
            'confidence': 0.75
        }
    else:
        return {
            'content': 'こんにちは！旅行の検索や予約のお手伝いをします。「検索」または「予約」とお聞かせください。',
            'intent': 'task_guidance',
            'confidence': 0.6
        }


def handle_rule_bot(message, session):
    """ルールベースBot（キーワード検出）の応答処理"""
    message_lower = message.lower()
    
    # キーワードベースの単純な応答
    if any(word in message for word in ['こんにちは', 'hello', 'はじめまして']):
        return {
            'content': 'こんにちは！bookiniad.comです。\n1. 旅行検索\n2. 予約確認\n3. よくある質問\n番号でお選びください。',
            'intent': 'greeting'
        }
    elif any(word in message for word in ['検索', '探す', '1']):
        return {
            'content': '旅行検索ですね。以下の情報を入力してください：\n• 出発地\n• 目的地\n• 出発日\n• 人数',
            'intent': 'search_menu'
        }
    elif any(word in message for word in ['予約', 'booking', '2']):
        return {
            'content': '予約確認ですね。予約番号を教えてください。',
            'intent': 'booking_inquiry'
        }
    elif any(word in message for word in ['faq', 'よくある質問', '質問', '3']):
        return {
            'content': 'よくある質問:\n• 予約のキャンセルは可能ですか？\n• 料金に含まれるものは？\n• 変更は可能ですか？',
            'intent': 'faq'
        }
    else:
        return {
            'content': '申し訳ございません。理解できませんでした。\n以下からお選びください：\n1. 旅行検索\n2. 予約確認\n3. よくある質問',
            'intent': 'fallback'
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
