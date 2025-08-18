from main.models import ChatMessage, Air, Accommodations
from django.db.models import Q


def handle_rule_bot(message, session):
    """ルールベースBot（キーワード検出）の応答処理"""
    # セッションから前回のintentを取得
    previous_messages = ChatMessage.objects.filter(session=session).order_by('-timestamp')[:2]
    last_bot_intent = None
    if previous_messages:
        for msg in previous_messages:
            if msg.message_type == 'rule_bot' and hasattr(msg, 'reasoning_process') and msg.reasoning_process:
                if isinstance(msg.reasoning_process, dict) and 'intent' in msg.reasoning_process:
                    last_bot_intent = msg.reasoning_process['intent']
                    break

    # 前回のintentに基づいて状態管理
    search_intents = [
        'search_menu', 'accommodation_search_start', 'flight_search_start', 'package_search_start',
        'location_detected', 'accommodation_location_set', 'accommodation_checkin_set',
        'accommodation_checkout_set', 'flight_departure_set', 'flight_destination_set', 'flight_date_set',
        "accommodation_location_retry", "flight_date_retry", "accommodation_checkin_retry", "accommodation_checkout_retry"
    ]

    if last_bot_intent in search_intents:
        # 検索モード：出発地や目的地の入力を受け付け
        return handle_search_input(message, session)
    elif last_bot_intent == 'booking_inquiry':
        # 予約照会モード：予約番号の入力を受け付け
        return handle_booking_number_input(message, session)

    # 初回またはリセット時の応答
    if any(word in message for word in ['こんにちは', 'hello', 'はじめまして', 'リセット', 'もどる']):
        return {
            'content': 'こんにちは！bookiniad.comです。\n1. 旅行検索\n2. 予約確認\n3. よくある質問\n番号でお選びください。',
            'intent': 'greeting',
            'reasoning': {'intent': 'greeting', 'state': 'initial'}
        }
    elif any(word in message for word in ['検索', '探す', '1']):
        return {
            'content': '旅行検索を開始します。\n\nまず、以下のいずれかをお選びください：\n• 宿泊施設検索：「宿泊」「ホテル」\n• 航空券検索：「航空券」「フライト」\n• パッケージ検索：「パッケージ」「セット」\n\n検索したい内容を入力してください。',
            'intent': 'search_menu',
            'reasoning': {'intent': 'search_menu', 'state': 'awaiting_search_type'}
        }
    elif any(word in message for word in ['予約', 'booking', '予約確認', '予約照会', '2']):
        return {
            'content': '予約確認を開始します。\n\n予約番号を教えてください。\n例: abc12345-def6-7890-ghij-klmnopqrstuv',
            'intent': 'booking_inquiry',
            'reasoning': {'intent': 'booking_inquiry', 'state': 'awaiting_reservation_number'}
        }
    elif any(word in message for word in ['faq', 'よくある質問', '質問', '3']):
        content = ('よくある質問:\n\n'
                   '• 予約のキャンセルは可能ですか？\n'
                   '  → 出発日の3日前まで可能です。\n\n'
                   '• 料金に含まれるものは？\n'
                   '  → 宿泊費、航空券代、税金が含まれます。\n\n'
                   '• 変更は可能ですか？\n'
                   '  → 出発日の7日前まで変更可能です。\n\n'
                   '他にご質問がありましたら「1」で検索、「2」で予約確認ができます。')
        return {
            'content': content,
            'intent': 'faq',
            'reasoning': {'intent': 'faq', 'state': 'faq_complete'}
        }
    else:
        return {
            'content': '申し訳ございません。理解できませんでした。\n\n以下からお選びください：\n1. 旅行検索\n2. 予約確認\n3. よくある質問\n\n「リセット」で最初に戻ります。',
            'intent': 'fallback',
            'reasoning': {'intent': 'fallback', 'state': 'error'}
        }


def handle_search_input(message, session):
    """検索入力を処理する関数"""

    # セッションから前回の状態を取得
    previous_messages = ChatMessage.objects.filter(session=session).order_by('-timestamp')[:5]
    last_bot_state = None
    last_search_type = None
    saved_location = None
    saved_checkin_date = None
    saved_checkout_date = None
    saved_departure = None
    saved_destination = None
    saved_departure_date = None

    if previous_messages:
        for msg in previous_messages:
            if msg.message_type == 'rule_bot' and hasattr(msg, 'reasoning_process') and msg.reasoning_process:
                if isinstance(msg.reasoning_process, dict):
                    if not last_bot_state:
                        last_bot_state = msg.reasoning_process.get('state')
                        last_search_type = msg.reasoning_process.get('search_type')

                    # 保存された情報を取得
                    if not saved_location and 'location' in msg.reasoning_process:
                        saved_location = msg.reasoning_process['location']
                    if not saved_checkin_date and 'checkin_date' in msg.reasoning_process:
                        saved_checkin_date = msg.reasoning_process['checkin_date']
                    if not saved_checkout_date and 'checkout_date' in msg.reasoning_process:
                        saved_checkout_date = msg.reasoning_process['checkout_date']
                    if not saved_departure and 'departure' in msg.reasoning_process:
                        saved_departure = msg.reasoning_process['departure']
                    if not saved_destination and 'destination' in msg.reasoning_process:
                        saved_destination = msg.reasoning_process['destination']
                    if not saved_departure_date and 'departure_date' in msg.reasoning_process:
                        saved_departure_date = msg.reasoning_process['departure_date']

    # 状態に応じた処理
    if last_bot_state == 'awaiting_location' and last_search_type == 'accommodation':
        # 宿泊地が入力された
        locations = ['東京', '大阪', '沖縄', '札幌', '京都', '福岡', '北海道', '神戸', '横浜', '名古屋']
        found_location = None
        for loc in locations:
            if loc in message:
                found_location = loc
                break

        if found_location:
            content = (f'{found_location}での宿泊施設検索ですね。\n\n'
                       'チェックイン日を教えてください。\n'
                       '例：2025-08-20 または 8月20日')
            return {
                'content': content,
                'intent': 'accommodation_location_set',
                'reasoning': {
                    'intent': 'accommodation_location_set',
                    'state': 'awaiting_checkin_date',
                    'search_type': 'accommodation',
                    'location': found_location
                }
            }
        else:
            content = ('宿泊地が見つかりませんでした。\n\n'
                       '以下の地域から選択してください：\n'
                       '東京、大阪、沖縄、札幌、京都、福岡、北海道')
            return {
                'content': content,
                'intent': 'accommodation_location_retry',
                'reasoning': {
                    'intent': 'accommodation_location_retry',
                    'state': 'awaiting_location',
                    'search_type': 'accommodation'
                }
            }

    elif last_bot_state == 'awaiting_checkin_date' and last_search_type == 'accommodation':
        # チェックイン日が入力された
        import re
        date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})月(\d{1,2})日'
        if re.search(date_pattern, message):
            content = ('チェックイン日を確認しました。\n\n'
                       'チェックアウト日を教えてください。\n'
                       '例：2025-08-22 または 8月22日')
            return {
                'content': content,
                'intent': 'accommodation_checkin_set',
                'reasoning': {
                    'intent': 'accommodation_checkin_set',
                    'state': 'awaiting_checkout_date',
                    'search_type': 'accommodation',
                    'location': saved_location,
                    'checkin_date': message
                }
            }
        else:
            content = ('日付の形式が正しくありません。\n\n'
                       '以下の形式で入力してください：\n'
                       '• 2025-08-20\n'
                       '• 8月20日')
            return {
                'content': content,
                'intent': 'accommodation_checkin_retry',
                'reasoning': {
                    'intent': 'accommodation_checkin_retry',
                    'state': 'awaiting_checkin_date',
                    'search_type': 'accommodation',
                    'location': saved_location
                }
            }
    
    elif last_bot_state == 'awaiting_checkout_date' and last_search_type == 'accommodation':
        # チェックアウト日が入力された
        import re
        date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})月(\d{1,2})日'
        if re.search(date_pattern, message):
            content = ('チェックアウト日を確認しました。\n\n'
                       '宿泊人数を教えてください。\n'
                       '例：2名 または 2人')
            return {
                'content': content,
                'intent': 'accommodation_checkout_set',
                'reasoning': {
                    'intent': 'accommodation_checkout_set',
                    'state': 'awaiting_guests',
                    'search_type': 'accommodation',
                    'location': saved_location,
                    'checkin_date': saved_checkin_date,
                    'checkout_date': message
                }
            }
        else:
            content = ('日付の形式が正しくありません。\n\n'
                       '以下の形式で入力してください：\n'
                       '• 2025-08-22\n'
                       '• 8月22日')
            return {
                'content': content,
                'intent': 'accommodation_checkout_retry',
                'reasoning': {
                    'intent': 'accommodation_checkout_retry',
                    'state': 'awaiting_checkout_date',
                    'search_type': 'accommodation',
                    'location': saved_location,
                    'checkin_date': saved_checkin_date
                }
            }
    
    elif last_bot_state == 'awaiting_guests' and last_search_type == 'accommodation':
        # 宿泊人数が入力された
        import re
        guest_pattern = r'(\d+)[名人]?'
        match = re.search(guest_pattern, message)
        if match:
            guests = match.group(1)
            location_display = saved_location or "指定の場所"
            checkin_display = saved_checkin_date or "指定日"
            checkout_display = saved_checkout_date or "指定日"
            
            # 実際の検索を実行
            search_results = perform_accommodation_search(
                saved_location, saved_checkin_date, saved_checkout_date, int(guests)
            )
            
            if search_results:
                # 宿泊日数を計算
                import re
                from datetime import datetime
                
                # チェックイン日とチェックアウト日から宿泊日数を計算
                nights = 1  # デフォルト
                try:
                    if saved_checkin_date and saved_checkout_date:
                        # 日付文字列をパース
                        checkin_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', saved_checkin_date)
                        checkout_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', saved_checkout_date)
                        
                        if checkin_match and checkout_match:
                            checkin = datetime(int(checkin_match.group(1)), int(checkin_match.group(2)), int(checkin_match.group(3)))
                            checkout = datetime(int(checkout_match.group(1)), int(checkout_match.group(2)), int(checkout_match.group(3)))
                            nights = (checkout - checkin).days
                except (ValueError, AttributeError):
                    nights = 1
                
                results_text = "\r\n".join([
                    (f"📍 {acc.name}\r\n"
                     f"   所在地: {acc.location}\r\n"
                     f"   ランク: {'⭐' * acc.rank} ({acc.rank}つ星)\r\n"
                     f"   料金: ¥{acc.price_per_night:,}/泊 (合計: ¥{acc.price_per_night * nights * int(guests):,})\r\n"
                     f"   説明: {acc.description[:60]}{'...' if len(acc.description) > 60 else ''}\r\n"
                     f"   設備: {', '.join(acc.amenities[:3]) if acc.amenities else 'なし'}")
                    for acc in search_results[:3]
                ])
                
                total_cost = sum(acc.price_per_night * nights * int(guests) for acc in search_results[:3])
                
                content = (f'宿泊人数{guests}名で確認しました。\r\n\r\n'
                           f'📋 検索条件:\r\n'
                           f'• 宿泊地: {location_display}\r\n'
                           f'• チェックイン: {checkin_display}\r\n'
                           f'• チェックアウト: {checkout_display}\r\n'
                           f'• 人数: {guests}名\r\n'
                           f'• 宿泊日数: {nights}泊\r\n\r\n'
                           f'🏨 検索結果 (上位{len(search_results[:3])}件):\r\n\r\n{results_text}\r\n\r\n'
                           f'💰 表示施設の平均料金: ¥{total_cost // len(search_results[:3]):,} (総額)\r\n\r\n'
                           '🔍 より詳細な検索は宿泊施設検索ページをご利用ください：\r\n'
                           '<a href="/accommodations/">こちら</a>\r\n\r\n'
                           '他にお手伝いできることはありますか？\r\n'
                           '「1」で検索、「リセット」で最初に戻ります。')
            else:
                content = (f'宿泊人数{guests}名で確認しました。\n\n'
                           f'📋 検索条件:\n'
                           f'• 宿泊地: {location_display}\n'
                           f'• チェックイン: {checkin_display}\n'
                           f'• チェックアウト: {checkout_display}\n'
                           f'• 人数: {guests}名\n\n'
                           '❌ 申し訳ございませんが、条件に合う宿泊施設が見つかりませんでした。\n\n'
                           '💡 検索のヒント:\n'
                           '• 宿泊地の表記を変えてみる（例：「東京」→「Tokyo」）\n'
                           '• 近隣エリアで検索してみる\n'
                           '• 日程を調整してみる\n\n'
                           '🔍 詳細な検索は宿泊施設検索ページをご利用ください：\n'
                           '<a href="/accommodations/">こちら</a>\n\n'
                           '他にお手伝いできることはありますか？\n'
                           '「1」で検索、「リセット」で最初に戻ります。')
            
            return {
                'content': content,
                'intent': 'accommodation_search_complete',
                'reasoning': {
                    'intent': 'accommodation_search_complete',
                    'state': 'search_complete',
                    'search_type': 'accommodation',
                    'location': saved_location,
                    'checkin_date': saved_checkin_date,
                    'checkout_date': saved_checkout_date,
                    'guests': guests,
                    'results_count': len(search_results) if search_results else 0
                }
            }
        else:
            content = ('人数がわかりませんでした。\n\n'
                       '以下の形式で入力してください：\n'
                       '• 2名\n'
                       '• 2人\n'
                       '• 2')
            return {
                'content': content,
                'intent': 'accommodation_guests_retry',
                'reasoning': {
                    'intent': 'accommodation_guests_retry',
                    'state': 'awaiting_guests',
                    'search_type': 'accommodation',
                    'location': saved_location,
                    'checkin_date': saved_checkin_date,
                    'checkout_date': saved_checkout_date
                }
            }
    
    elif last_bot_state == 'awaiting_departure' and last_search_type == 'flight':
        # 出発地が入力された
        locations = ['東京', '大阪', '沖縄', '札幌', '京都', '福岡', '北海道', '神戸', '横浜', '名古屋']
        found_location = None
        for loc in locations:
            if loc in message:
                found_location = loc
                break
        
        if found_location:
            content = (f'{found_location}からの出発ですね。\n\n'
                       '目的地を教えてください。\n'
                       '例：沖縄、福岡、北海道')
            return {
                'content': content,
                'intent': 'flight_departure_set',
                'reasoning': {
                    'intent': 'flight_departure_set',
                    'state': 'awaiting_destination',
                    'search_type': 'flight',
                    'departure': found_location
                }
            }
        else:
            content = ('出発地が見つかりませんでした。\n\n'
                       '以下の地域から選択してください：\n'
                       '東京、大阪、沖縄、札幌、京都、福岡、北海道')
            return {
                'content': content,
                'intent': 'flight_departure_retry',
                'reasoning': {
                    'intent': 'flight_departure_retry',
                    'state': 'awaiting_departure',
                    'search_type': 'flight'
                }
            }
    
    elif last_bot_state == 'awaiting_destination' and last_search_type == 'flight':
        # 目的地が入力された
        locations = ['東京', '大阪', '沖縄', '札幌', '京都', '福岡', '北海道', '神戸', '横浜', '名古屋']
        found_location = None
        for loc in locations:
            if loc in message:
                found_location = loc
                break
        
        if found_location:
            content = (f'{found_location}への航空券ですね。\n\n'
                       '出発日を教えてください。\n'
                       '例：2025-08-20 または 8月20日')
            return {
                'content': content,
                'intent': 'flight_destination_set',
                'reasoning': {
                    'intent': 'flight_destination_set',
                    'state': 'awaiting_departure_date',
                    'search_type': 'flight',
                    'departure': saved_departure,
                    'destination': found_location
                }
            }
        else:
            content = ('目的地が見つかりませんでした。\n\n'
                       '以下の地域から選択してください：\n'
                       '東京、大阪、沖縄、札幌、京都、福岡、北海道')
            return {
                'content': content,
                'intent': 'flight_destination_retry',
                'reasoning': {
                    'intent': 'flight_destination_retry',
                    'state': 'awaiting_destination',
                    'search_type': 'flight',
                    'departure': saved_departure
                }
            }
    
    elif last_bot_state == 'awaiting_departure_date' and last_search_type == 'flight':
        # 出発日が入力された
        import re
        date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})月(\d{1,2})日'
        if re.search(date_pattern, message):
            content = ('出発日を確認しました。\n\n'
                       '搭乗者数を教えてください。\n'
                       '例：2名 または 2人')
            return {
                'content': content,
                'intent': 'flight_date_set',
                'reasoning': {
                    'intent': 'flight_date_set',
                    'state': 'awaiting_passengers',
                    'search_type': 'flight',
                    'departure': saved_departure,
                    'destination': saved_destination,
                    'departure_date': message
                }
            }
        else:
            content = ('日付の形式が正しくありません。\n\n'
                       '以下の形式で入力してください：\n'
                       '• 2025-08-20\n'
                       '• 8月20日')
            return {
                'content': content,
                'intent': 'flight_date_retry',
                'reasoning': {
                    'intent': 'flight_date_retry',
                    'state': 'awaiting_departure_date',
                    'search_type': 'flight',
                    'departure': saved_departure,
                    'destination': saved_destination
                }
            }
    
    elif last_bot_state == 'awaiting_passengers' and last_search_type == 'flight':
        # 搭乗者数が入力された
        import re
        passenger_pattern = r'(\d+)[名人]?'
        match = re.search(passenger_pattern, message)
        if match:
            passengers = match.group(1)
            departure_display = saved_departure or "指定の出発地"
            destination_display = saved_destination or "指定の目的地"
            date_display = saved_departure_date or "指定日"
            
            # 実際の検索を実行
            search_results = perform_flight_search(
                saved_departure, saved_destination, saved_departure_date, int(passengers)
            )
            
            if search_results:
                results_text = "\r\n".join([
                    (f"✈️ {flight.name} {flight.flight_number}\r\n"
                     f"   路線: {flight.place_from} → {flight.place_to}\r\n"
                     f"   出発: {flight.departure_time.strftime('%H:%M')} 到着: {flight.arrival_time.strftime('%H:%M')}\r\n"
                     f"   料金: ¥{flight.fee:,}/人 (合計: ¥{flight.fee * int(passengers):,})\r\n"
                     f"   空席: {flight.available_seats}席\r\n"
                     f"   便種別: {flight.get_flight_type_display()}")
                    for flight in search_results[:3]
                ])
                
                total_cost = sum(flight.fee * int(passengers) for flight in search_results[:3])
                
                content = (f'搭乗者数{passengers}名で確認しました。\r\n\r\n'
                           f'📋 検索条件:\r\n'
                           f'• 出発地: {departure_display}\r\n'
                           f'• 目的地: {destination_display}\r\n'
                           f'• 出発日: {date_display}\r\n'
                           f'• 搭乗者数: {passengers}名\r\n\r\n'
                           f'✈️ 検索結果 (上位{len(search_results[:3])}件):\r\n\r\n{results_text}\r\n\r\n'
                           f'💰 表示便の平均料金: ¥{total_cost // len(search_results[:3]):,} (総額)\r\n\r\n'
                           '🔍 より詳細な検索は航空券検索ページをご利用ください：\r\n'
                           '<a href="/flights/">こちら</a>\r\n\r\n'
                           '他にお手伝いできることはありますか？\r\n'
                           '「1」で検索、「リセット」で最初に戻ります。')
            else:
                content = (f'搭乗者数{passengers}名で確認しました。\n\n'
                           f'📋 検索条件:\n'
                           f'• 出発地: {departure_display}\n'
                           f'• 目的地: {destination_display}\n'
                           f'• 出発日: {date_display}\n'
                           f'• 搭乗者数: {passengers}名\n\n'
                           '❌ 申し訳ございませんが、条件に合う航空券が見つかりませんでした。\n\n'
                           '💡 検索のヒント:\n'
                           '• 出発地・目的地の表記を確認\n'
                           '• 日程を前後に調整してみる\n'
                           '• 別の空港を検討してみる\n\n'
                           '🔍 詳細な検索は航空券検索ページをご利用ください：\n'
                           '<a href="/flights/">こちら</a>\n\n'
                           '他にお手伝いできることはありますか？\n'
                           '「1」で検索、「リセット」で最初に戻ります。')
            
            return {
                'content': content,
                'intent': 'flight_search_complete',
                'reasoning': {
                    'intent': 'flight_search_complete',
                    'state': 'search_complete',
                    'search_type': 'flight',
                    'departure': saved_departure,
                    'destination': saved_destination,
                    'departure_date': saved_departure_date,
                    'passengers': passengers,
                    'results_count': len(search_results) if search_results else 0
                }
            }
        else:
            content = ('搭乗者数がわかりませんでした。\n\n'
                       '以下の形式で入力してください：\n'
                       '• 2名\n'
                       '• 2人\n'
                       '• 2')
            return {
                'content': content,
                'intent': 'flight_passengers_retry',
                'reasoning': {
                    'intent': 'flight_passengers_retry',
                    'state': 'awaiting_passengers',
                    'search_type': 'flight',
                    'departure': saved_departure,
                    'destination': saved_destination,
                    'departure_date': saved_departure_date
                }
            }
    
    # 初回の検索タイプ選択または「リセット」コマンド
    if any(word in message for word in ['宿泊', 'ホテル', '泊まる']):
        content = ('宿泊施設検索を選択されました。\n\n'
                   '以下の情報を順番に教えてください：\n\n'
                   '1. 宿泊地（例：東京、大阪、沖縄）\n'
                   '2. チェックイン日（例：2025-08-20）\n'
                   '3. チェックアウト日（例：2025-08-22）\n'
                   '4. 宿泊人数（例：2名）\n\n'
                   'まずは宿泊地を教えてください。')
        return {
            'content': content,
            'intent': 'accommodation_search_start',
            'reasoning': {
                'intent': 'accommodation_search_start',
                'state': 'awaiting_location',
                'search_type': 'accommodation'
            }
        }
    elif any(word in message for word in ['航空券', 'フライト', '飛行機']):
        content = ('航空券検索を選択されました。\n\n'
                   '以下の情報を順番に教えてください：\n\n'
                   '1. 出発地（例：東京、大阪）\n'
                   '2. 目的地（例：沖縄、福岡）\n'
                   '3. 出発日（例：2025-08-20）\n'
                   '4. 搭乗者数（例：2名）\n\n'
                   'まずは出発地を教えてください。')
        return {
            'content': content,
            'intent': 'flight_search_start',
            'reasoning': {
                'intent': 'flight_search_start',
                'state': 'awaiting_departure',
                'search_type': 'flight'
            }
        }
    elif any(word in message for word in ['パッケージ', 'セット', '旅行']):
        content = ('パッケージ検索を選択されました。\n\n'
                   '人気のパッケージをご紹介します：\n\n'
                   '• 沖縄3日間パッケージ - ¥50,000\n'
                   '• 北海道2泊3日 - ¥45,000\n'
                   '• 京都観光パッケージ - ¥35,000\n\n'
                   '詳細な検索をご希望の場合は、出発地と目的地を教えてください。\n'
                   '例：「東京から沖縄」')
        return {
            'content': content,
            'intent': 'package_search_start',
            'reasoning': {
                'intent': 'package_search_start',
                'state': 'showing_popular_packages',
                'search_type': 'package'
            }
        }
    elif any(word in message for word in ['リセット', 'もどる', '戻る', '最初']):
        # 検索をリセットして最初に戻る
        return {
            'content': 'こんにちは！bookiniad.comです。\n1. 旅行検索\n2. 予約確認\n3. よくある質問\n番号でお選びください。',
            'intent': 'greeting',
            'reasoning': {'intent': 'greeting', 'state': 'initial'}
        }
    else:
        # 地名らしきものが含まれているかチェック
        locations = ['東京', '大阪', '沖縄', '札幌', '京都', '福岡', '北海道', '神戸', '横浜', '名古屋']
        found_locations = [loc for loc in locations if loc in message]
        
        if found_locations:
            location = found_locations[0]
            content = (f'{location}での検索ですね。\n\n'
                       '検索タイプを選択してください：\n'
                       f'• 宿泊施設：「{location}のホテル」\n'
                       f'• 航空券：「{location}への航空券」\n'
                       f'• パッケージ：「{location}のパッケージ」\n\n'
                       'または、より具体的な条件を教えてください。')
            return {
                'content': content,
                'intent': 'location_detected',
                'reasoning': {
                    'intent': 'location_detected',
                    'state': 'awaiting_search_refinement',
                    'detected_location': location
                }
            }
        else:
            return {
                'content': '検索内容を理解できませんでした。\n\n以下から選択してください：\n• 宿泊施設検索：「宿泊」「ホテル」\n• 航空券検索：「航空券」「フライト」\n• パッケージ検索：「パッケージ」「セット」\n\nまたは「リセット」で最初に戻ります。',
                'intent': 'search_error',
                'reasoning': {'intent': 'search_error', 'state': 'search_input_error'}
            }


def handle_booking_number_input(message, session):
    """予約番号入力を処理する関数"""
    
    # 予約番号らしき文字列をチェック（UUIDの形式など）
    import re
    
    # ハイフンを含む長い文字列を予約番号と仮定
    reservation_pattern = r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'
    
    if re.search(reservation_pattern, message):
        # 実際の予約照会を試行
        reservation_number = re.search(reservation_pattern, message).group()
        
        try:
            from main.models import Booking
            import uuid
            
            try:
                # UUIDオブジェクトとして変換を試行
                uuid_obj = uuid.UUID(reservation_number)
                booking = Booking.objects.get(reservation_number=uuid_obj)
            except ValueError:
                # UUID形式でない場合は文字列として検索
                booking = Booking.objects.get(reservation_number=reservation_number)
            
            # 予約が見つかった場合
            hotel_name = booking.accommodations.name if booking.accommodations else "なし"
            content = (f'予約が見つかりました！\n\n'
                       f'予約番号: {reservation_number}\n'
                       f'宿泊施設: {hotel_name}\n'
                       f'宿泊人数: {booking.num_of_people}名\n'
                       f'合計料金: ¥{booking.total_fee:,}\n\n'
                       '詳細はこちらのリンクで確認できます：\n'
                       '/booking/inquiry/\n\n'
                       '他にお手伝いできることはありますか？'
                       '「1」で検索、「リセット」で最初に戻ります。')
            return {
                'content': content,
                'intent': 'booking_found',
                'reasoning': {
                    'intent': 'booking_found',
                    'state': 'booking_details_shown',
                    'reservation_number': reservation_number
                }
            }
        except Booking.DoesNotExist:
            content = (f'申し訳ございません。予約番号「{reservation_number}」が見つかりませんでした。\n\n'
                       '予約番号をもう一度確認して入力してください。\n\n'
                       '例: abc12345-def6-7890-ghij-klmnopqrstuv\n\n'
                       '「リセット」で最初に戻ります。')
            return {
                'content': content,
                'intent': 'booking_not_found',
                'reasoning': {
                    'intent': 'booking_not_found',
                    'state': 'reservation_not_found',
                    'input': reservation_number
                }
            }
    else:
        return {
            'content': '予約番号の形式が正しくないようです。\n\n予約番号は以下のような形式です：\nabc12345-def6-7890-ghij-klmnopqrstuv\n\n正しい予約番号を入力してください。\n\n「リセット」で最初に戻ります。',
            'intent': 'invalid_reservation_format',
            'reasoning': {'intent': 'invalid_reservation_format', 'state': 'format_error', 'input': message}
        }


def perform_accommodation_search(location, checkin_date, checkout_date, guests):
    """宿泊施設検索を実行"""
    try:
        # Accommodationsモデルから検索
        queryset = Accommodations.objects.all()
        
        # 場所での絞り込み（locationとnameの両方で検索）
        if location:
            queryset = queryset.filter(
                Q(location__icontains=location) | Q(name__icontains=location)
            )
        
        # 宿泊人数での絞り込み（total_roomsが1以上のもの）
        if guests:
            queryset = queryset.filter(total_rooms__gte=1)
        
        # 料金順でソート（安い順）
        queryset = queryset.order_by('price_per_night')
        
        # 最大10件まで返す
        return queryset[:10]
        
    except Exception as e:
        print(f"Accommodation search error: {e}")
        return []


def perform_flight_search(departure, destination, departure_date, passengers):
    """航空券検索を実行"""
    from datetime import datetime
    
    try:
        # Airモデルから検索
        queryset = Air.objects.all()
        
        # 出発地での絞り込み
        if departure:
            queryset = queryset.filter(place_from__icontains=departure)
        
        # 目的地での絞り込み
        if destination:
            queryset = queryset.filter(place_to__icontains=destination)
        
        # 最大10件まで返す
        return queryset[:10]
        
    except Exception as e:
        print(f"Flight search error: {e}")
        return []

