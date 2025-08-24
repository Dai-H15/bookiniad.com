from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import date, timedelta, datetime
from django.utils import timezone
from main.models import Accommodations, Air, TravelPackage, AccommodationAvailability, FlightAvailability


class Command(BaseCommand):
    help = 'bookiniad.comの初期サンプルデータを作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='既存のデータを削除してから作成',
        )
        parser.add_argument(
            '--availability-days',
            type=int,
            default=30,
            help='空き状況データを作成する日数（デフォルト: 30日）',
        )
        parser.add_argument(
            '--skip-availability',
            action='store_true',
            help='空き状況データの作成をスキップ',
        )

    def create_future_flights(self, availability_days):
        """air.jsonのベースデータから複数日分の航空券を作成"""
        from datetime import datetime, timedelta
        
        # 現在の日付を取得
        today = date.today()
        
        # ベースとなる航空券データを取得（air.jsonからロードされたもの）
        base_flights = Air.objects.all()
        
        self.stdout.write(f'  ベース航空券数: {base_flights.count()}件')
        
        new_flights_created = 0
        
        # 指定された日数分、未来の日付で航空券を作成
        for days_ahead in range(1, availability_days + 1):
            target_date = today + timedelta(days=days_ahead)
            
            # その日付の航空券が既に存在するかチェック（departure_timeの日付部分で比較）
            existing_count = Air.objects.filter(departure_time__date=target_date).count()
            if existing_count > 0:
                continue
                
            # ベース航空券をコピーして新しい日付で作成
            for base_flight in base_flights:
                # 元の時刻を保持しながら日付のみ変更
                original_departure = base_flight.departure_time
                original_arrival = base_flight.arrival_time
                
                new_departure_time = datetime.combine(
                    target_date, 
                    original_departure.time()
                ).replace(tzinfo=original_departure.tzinfo)
                
                # 到着時刻も同じ日数分シフト
                date_diff = target_date - original_departure.date()
                new_arrival_time = original_arrival + date_diff
                
                new_flight = Air(
                    name=base_flight.name,
                    flight_number=base_flight.flight_number,
                    flight_type=base_flight.flight_type,
                    place_from=base_flight.place_from,
                    place_to=base_flight.place_to,
                    departure_time=new_departure_time,
                    arrival_time=new_arrival_time,
                    fee=base_flight.fee,
                    available_seats=base_flight.available_seats
                )
                new_flight.save()
                new_flights_created += 1
        
        self.stdout.write(f'  新規作成した航空券数: {new_flights_created}件')

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('既存データを削除中...')
            TravelPackage.objects.all().delete()
            Air.objects.all().delete()
            Accommodations.objects.all().delete()
            AccommodationAvailability.objects.all().delete()
            FlightAvailability.objects.all().delete()
            self.stdout.write(self.style.WARNING('既存データを削除しました'))

        # fixtureファイルからデータを読み込み
        self.stdout.write('fixtureファイルからデータを読み込み中...')
        
        try:
            # 宿泊施設データを読み込み
            self.stdout.write('宿泊施設データを読み込み中...')
            call_command('loaddata', 'main/fixtures/accommodations.json')
            self.stdout.write(f'  ✓ 宿泊施設データを読み込みました: {Accommodations.objects.count()}件')
            
            # 航空券データを読み込み
            self.stdout.write('航空券データを読み込み中...')
            call_command('loaddata', 'main/fixtures/air.json')
            base_flight_count = Air.objects.count()
            self.stdout.write(f'  ✓ ベース航空券データを読み込みました: {base_flight_count}件')
            
            # 航空券データを複数日分に拡張
            self.stdout.write('複数日分の航空券データを作成中...')
            self.create_future_flights(options['availability_days'])
            total_flight_count = Air.objects.count()
            self.stdout.write(f'  ✓ 航空券データを拡張しました: {total_flight_count}件（+{total_flight_count - base_flight_count}件）')
            
            # 旅行パッケージデータを動的に作成
            self.stdout.write('旅行パッケージデータを動的作成中...')
            self.create_travel_packages()
            self.stdout.write(f'  ✓ 旅行パッケージデータを作成しました: {TravelPackage.objects.count()}件')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'データの読み込み中にエラーが発生しました: {str(e)}')
            )
            return

        # 空き状況データの作成
        if not options['skip_availability']:
            self.stdout.write('\n空き状況データを作成中...')
            try:
                self.create_availability_data(options['availability_days'])
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'空き状況データの作成中にエラーが発生しました: {str(e)}')
                )
                return

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ fixtureからのデータ読み込みが完了しました！\n'
                f'   宿泊施設: {Accommodations.objects.count()}件\n'
                f'   航空券: {Air.objects.count()}件\n'
                f'   パッケージ: {TravelPackage.objects.count()}件\n'
                f'   宿泊施設空き状況: {AccommodationAvailability.objects.count()}件\n'
                f'   航空券空き状況: {FlightAvailability.objects.count()}件'
            )
        )

    def create_availability_data(self, days):
        """空き状況データを作成"""
        start_date = date.today()
        
        # 宿泊施設の空き状況データを作成
        self.stdout.write('宿泊施設の空き状況データを作成中...')
        accommodations = Accommodations.objects.all()
        
        accommodation_count = 0
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            for accommodation in accommodations:
                # 基本的に総部屋数の80%を空室として設定
                available_rooms = int(accommodation.total_rooms * 0.8)
                
                # 週末や特定の日は空室を少なくする
                if current_date.weekday() in [4, 5]:  # 金曜日、土曜日
                    available_rooms = int(accommodation.total_rooms * 0.3)
                elif current_date.weekday() == 6:  # 日曜日
                    available_rooms = int(accommodation.total_rooms * 0.5)
                
                AccommodationAvailability.objects.get_or_create(
                    accommodation=accommodation,
                    date=current_date,
                    defaults={'available_rooms': available_rooms}
                )
                accommodation_count += 1
        
        self.stdout.write(f'  ✓ 宿泊施設の空き状況データ: {accommodation_count}件')
        
        # 航空券の空き状況データを作成
        self.stdout.write('航空券の空き状況データを作成中')
        flights = Air.objects.all()
        total_flights = flights.count()
        
        flight_count = 0
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            # 日付ごとの進捗表示
            self.stdout.write(f"\n  日付: {current_date.strftime('%Y-%m-%d')} ({i+1}/{days}日目)", ending="")
            
            for j, flight in enumerate(flights):
                # 進捗表示（10件ごと、または最後の件）
                if j % 100 == 0 or j == total_flights - 1:
                    self.stdout.write(f" [{j+1}/{total_flights}]", ending="")
                    self.stdout.flush()
                
                # 基本的に総座席数の70%を空席として設定
                available_seats = int(flight.available_seats * 0.7)
                
                # 週末や特定の日は空席を少なくする
                if current_date.weekday() in [4, 5]:  # 金曜日、土曜日
                    available_seats = int(flight.available_seats * 0.4)
                elif current_date.weekday() == 6:  # 日曜日
                    available_seats = int(flight.available_seats * 0.5)
                
                FlightAvailability.objects.get_or_create(
                    flight=flight,
                    date=current_date,
                    defaults={'available_seats': available_seats}
                )
                flight_count += 1
        
        self.stdout.write(f'\n  ✓ 航空券の空き状況データ: {flight_count}件')

    def create_travel_packages(self):
        """航空券データと宿泊施設データを使って旅行パッケージを動的に作成"""
        
        # パッケージテンプレート
        package_templates = [
            {
                'name': '東京⇔大阪ビジネス出張プラン',
                'description': '効率的なビジネス出張に最適。新幹線より快適な空の旅で、時間を有効活用。大阪駅前のホテルで移動も楽々。',
                'outbound_route': ('東京', '大阪'),
                'return_route': ('大阪', '東京'),
                'accommodation_location': '大阪',
                'stay_duration': 2,
                'is_available': False
            },
            {
                'name': '沖縄リゾート満喫3泊4日',
                'description': '美しい沖縄の海を満喫できるリゾートパッケージ。家族連れやカップルに人気。ビーチアクセス抜群のホテルでゆったり過ごせます。',
                'outbound_route': ('東京', '沖縄'),
                'return_route': ('沖縄', '東京'),
                'accommodation_location': '沖縄',
                'stay_duration': 3,
                'is_available': False
            },
            {
                'name': '北海道グルメ旅行',
                'description': '北海道の新鮮な海鮮とスープカレーを満喫。雪景色も楽しめる冬の北海道を堪能できます。',
                'outbound_route': ('東京', '札幌'),
                'return_route': ('札幌', '東京'),
                'accommodation_location': '札幌',
                'stay_duration': 2,
                'is_available': False
            },
            {
                'name': '沖縄ビーチリゾート',
                'description': '沖縄で極上のバケーション。綺麗な海を一望できるホテルで、バケーション',
                'outbound_route': ('東京', '沖縄'),
                'return_route': ('沖縄', '東京'),
                'accommodation_location': '沖縄',
                'stay_duration': 4,
                'is_available': False
            },
            {
                'name': '大阪グルメツアー',
                'description': '本場の韓国料理を食べ尽くす美食の旅。明洞での買い物も楽しめる充実プラン。',
                'outbound_route': ('東京', '大阪'),
                'return_route': ('大阪', '東京'),
                'accommodation_location': '大阪',  # ソウルのホテルがないため東京で代用
                'stay_duration': 2,
                'is_available': False
            }
        ]
        
        created_count = 0
        
        for template in package_templates:
            try:
                # 往路航空券を検索（air.jsonの航空券を使用）
                outbound_flights = Air.objects.filter(
                    place_from=template['outbound_route'][0],
                    place_to=template['outbound_route'][1]
                ).first()
                
                # 復路航空券を検索
                return_flights = Air.objects.filter(
                    place_from=template['return_route'][0],
                    place_to=template['return_route'][1]
                ).first()
                
                # 宿泊施設を検索
                accommodation = Accommodations.objects.filter(
                    location__icontains=template['accommodation_location']
                ).first()
                
                # デバッグ情報を表示
                self.stdout.write(f'  検索中: {template["name"]}')
                self.stdout.write(f'    往路: {template["outbound_route"]} -> {outbound_flights.flight_number if outbound_flights else "見つかりません"}')
                self.stdout.write(f'    復路: {template["return_route"]} -> {return_flights.flight_number if return_flights else "見つかりません"}')
                self.stdout.write(f'    宿泊: {template["accommodation_location"]} -> {accommodation.name if accommodation else "見つかりません"}')
                
                if outbound_flights and return_flights and accommodation:
                    # 総額を計算
                    total_price = (
                        outbound_flights.fee +
                        return_flights.fee +
                        (accommodation.price_per_night * template['stay_duration'])
                    )
                    
                    # パッケージ作成
                    TravelPackage.objects.create(
                        name=template['name'],
                        description=template['description'],
                        total_price=total_price,
                        outbound_flight=outbound_flights,
                        return_flight=return_flights,
                        accommodation=accommodation,
                        stay_duration=template['stay_duration'],
                        is_available=template['is_available']
                    )
                    created_count += 1
                else:
                    self.stdout.write(f'  ⚠️ パッケージ "{template["name"]}" をスキップ（必要なデータが見つかりません）')
                    
            except Exception as e:
                self.stdout.write(f'  ⚠️ パッケージ "{template["name"]}" の作成でエラー: {str(e)}')
        
        self.stdout.write(f'  ✓ {created_count}件の旅行パッケージを作成しました')
