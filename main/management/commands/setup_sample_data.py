from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from datetime import date, datetime, timedelta, time
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
            
            # 航空券データを動的に作成
            self.stdout.write('航空券データを動的作成中...')
            self.create_flight_data(options['availability_days'])
            self.stdout.write(f'  ✓ 航空券データを作成しました: {Air.objects.count()}件')
            
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
        
        flight_count = 0
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            self.stdout.write("=", ending="")
            self.stdout.flush()
            for flight in flights:
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
        self.stdout.write(">", ending="")
        self.stdout.flush()
        self.stdout.write(f'  ✓ 航空券の空き状況データ: {flight_count}件')

    def create_flight_data(self, days):
        """指定された期間分の航空券データを動的に作成"""
        
        # 基本的な航空券テンプレート
        flight_templates = [
            # 国内線 - ANATA
            {
                'name': 'ANATA エコノミー', 'flight_number': 'SF101', 'flight_type': 'domestic',
                'place_from': '東京', 'place_to': '大阪', 'fee': 18000, 'available_seats': 8,
                'departure_time': time(6, 0), 'arrival_time': time(7, 15)
            },
            {
                'name': 'ANATA ビジネス', 'flight_number': 'SF102', 'flight_type': 'domestic',
                'place_from': '東京', 'place_to': '大阪', 'fee': 35000, 'available_seats': 4,
                'departure_time': time(8, 30), 'arrival_time': time(9, 45)
            },
            {
                'name': 'ANATA エコノミー', 'flight_number': 'SF103', 'flight_type': 'domestic',
                'place_from': '大阪', 'place_to': '東京', 'fee': 18000, 'available_seats': 8,
                'departure_time': time(14, 20), 'arrival_time': time(15, 35)
            },
            {
                'name': 'ANATA ビジネス', 'flight_number': 'SF104', 'flight_type': 'domestic',
                'place_from': '大阪', 'place_to': '東京', 'fee': 35000, 'available_seats': 4,
                'departure_time': time(16, 50), 'arrival_time': time(18, 5)
            },
            
            # 国内線 - JALJAL
            {
                'name': 'JALJAL エコノミー', 'flight_number': 'BG201', 'flight_type': 'domestic',
                'place_from': '東京', 'place_to': '北海道', 'fee': 25000, 'available_seats': 12,
                'departure_time': time(7, 0), 'arrival_time': time(8, 45)
            },
            {
                'name': 'JALJAL プレミアム', 'flight_number': 'BG202', 'flight_type': 'domestic',
                'place_from': '東京', 'place_to': '北海道', 'fee': 45000, 'available_seats': 6,
                'departure_time': time(10, 30), 'arrival_time': time(12, 15)
            },
            {
                'name': 'JALJAL エコノミー', 'flight_number': 'BG203', 'flight_type': 'domestic',
                'place_from': '北海道', 'place_to': '東京', 'fee': 25000, 'available_seats': 12,
                'departure_time': time(15, 0), 'arrival_time': time(16, 45)
            },
            {
                'name': 'JALJAL プレミアム', 'flight_number': 'BG204', 'flight_type': 'domestic',
                'place_from': '北海道', 'place_to': '東京', 'fee': 45000, 'available_seats': 6,
                'departure_time': time(18, 20), 'arrival_time': time(20, 5)
            },
            
            # 国内線 - ジェットスカイ
            {
                'name': 'ジェットスカイ エコノミー', 'flight_number': 'PZ301', 'flight_type': 'domestic',
                'place_from': '東京', 'place_to': '沖縄', 'fee': 32000, 'available_seats': 10,
                'departure_time': time(8, 45), 'arrival_time': time(11, 30)
            },
            {
                'name': 'ジェットスカイ ビジネス', 'flight_number': 'PZ302', 'flight_type': 'domestic',
                'place_from': '東京', 'place_to': '沖縄', 'fee': 58000, 'available_seats': 5,
                'departure_time': time(13, 15), 'arrival_time': time(16, 0)
            },
            {
                'name': 'ジェットスカイ エコノミー', 'flight_number': 'PZ303', 'flight_type': 'domestic',
                'place_from': '沖縄', 'place_to': '東京', 'fee': 32000, 'available_seats': 10,
                'departure_time': time(12, 0), 'arrival_time': time(14, 45)
            },
            {
                'name': 'ジェットスカイ ビジネス', 'flight_number': 'PZ304', 'flight_type': 'domestic',
                'place_from': '沖縄', 'place_to': '東京', 'fee': 58000, 'available_seats': 5,
                'departure_time': time(17, 30), 'arrival_time': time(20, 15)
            },
            
            # 国際線 - アナコンダ航空
            {
                'name': 'アナコンダ航空 エコノミー', 'flight_number': 'GD401', 'flight_type': 'international',
                'place_from': '東京', 'place_to': 'ハワイ', 'fee': 85000, 'available_seats': 20,
                'departure_time': time(10, 0), 'arrival_time': time(22, 30)
            },
            {
                'name': 'アナコンダ航空 ビジネス', 'flight_number': 'GD402', 'flight_type': 'international',
                'place_from': '東京', 'place_to': 'ハワイ', 'fee': 180000, 'available_seats': 8,
                'departure_time': time(14, 0), 'arrival_time': time(2, 30)
            },
            {
                'name': 'アナコンダ航空 エコノミー', 'flight_number': 'GD403', 'flight_type': 'international',
                'place_from': 'ハワイ', 'place_to': '東京', 'fee': 85000, 'available_seats': 20,
                'departure_time': time(11, 0), 'arrival_time': time(15, 30)
            },
            {
                'name': 'アナコンダ航空 ビジネス', 'flight_number': 'GD404', 'flight_type': 'international',
                'place_from': 'ハワイ', 'place_to': '東京', 'fee': 180000, 'available_seats': 8,
                'departure_time': time(16, 0), 'arrival_time': time(20, 30)
            },
            
            # 国際線 - ワールド・タコス航空
            {
                'name': 'ワールド・タコス航空 エコノミー', 'flight_number': 'WT501', 'flight_type': 'international',
                'place_from': '東京', 'place_to': 'ソウル', 'fee': 45000, 'available_seats': 15,
                'departure_time': time(9, 30), 'arrival_time': time(11, 45)
            },
            {
                'name': 'ワールド・タコス航空 プレミアム', 'flight_number': 'WT502', 'flight_type': 'international',
                'place_from': '東京', 'place_to': 'ソウル', 'fee': 85000, 'available_seats': 7,
                'departure_time': time(15, 0), 'arrival_time': time(17, 15)
            },
            {
                'name': 'ワールド・タコス航空 エコノミー', 'flight_number': 'WT503', 'flight_type': 'international',
                'place_from': 'ソウル', 'place_to': '東京', 'fee': 45000, 'available_seats': 15,
                'departure_time': time(13, 20), 'arrival_time': time(15, 35)
            },
            {
                'name': 'ワールド・タコス航空 プレミアム', 'flight_number': 'WT504', 'flight_type': 'international',
                'place_from': 'ソウル', 'place_to': '東京', 'fee': 85000, 'available_seats': 7,
                'departure_time': time(19, 45), 'arrival_time': time(22, 0)
            }
        ]
        
        # 指定された期間分の航空券を作成
        start_date = date.today()
        created_count = 0
        
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            
            for template in flight_templates:
                # 出発日時と到着日時を作成（タイムゾーン対応）
                departure_datetime = timezone.make_aware(
                    datetime.combine(current_date, template['departure_time'])
                )
                arrival_datetime = timezone.make_aware(
                    datetime.combine(current_date, template['arrival_time'])
                )
                
                # 到着時刻が翌日になる場合の調整
                if template['arrival_time'] < template['departure_time']:
                    arrival_datetime = timezone.make_aware(
                        datetime.combine(current_date + timedelta(days=1), template['arrival_time'])
                    )
                
                # 航空券オブジェクトを作成
                Air.objects.create(
                    name=template['name'],
                    flight_number=f"{template['flight_number']}_{current_date.strftime('%Y%m%d')}",
                    flight_type=template['flight_type'],
                    place_from=template['place_from'],
                    place_to=template['place_to'],
                    departure_time=departure_datetime,
                    arrival_time=arrival_datetime,
                    fee=template['fee'],
                    available_seats=template['available_seats']
                )
                created_count += 1
        
        self.stdout.write(f'  ✓ {created_count}件の航空券データを作成しました')
        self.stdout.write(f'  ✓ {len(flight_templates)}の基本便種 × {days}日間 = {created_count}件')
    
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
                'outbound_route': ('東京', '北海道'),
                'return_route': ('北海道', '東京'),
                'accommodation_location': '札幌',
                'stay_duration': 2,
                'is_available': False
            },
            {
                'name': 'ハワイ・ワイキキビーチリゾート',
                'description': '憧れのハワイで極上のバケーション。ワイキキビーチを一望できるホテルで、南国の風を感じてください。',
                'outbound_route': ('東京', 'ハワイ'),
                'return_route': ('ハワイ', '東京'),
                'accommodation_location': '沖縄',  # ハワイのホテルがないため沖縄で代用
                'stay_duration': 4,
                'is_available': False
            },
            {
                'name': 'ソウル・韓国グルメツアー',
                'description': '本場の韓国料理を食べ尽くす美食の旅。明洞での買い物も楽しめる充実プラン。',
                'outbound_route': ('東京', 'ソウル'),
                'return_route': ('ソウル', '東京'),
                'accommodation_location': '福岡',  # ソウルのホテルがないため福岡で代用
                'stay_duration': 2,
                'is_available': False
            }
        ]
        
        created_count = 0
        
        for template in package_templates:
            try:
                # 往路航空券を検索（今日の便を使用）
                today = date.today()
                outbound_flights = Air.objects.filter(
                    place_from=template['outbound_route'][0],
                    place_to=template['outbound_route'][1],
                    departure_time__date=today
                ).first()
                
                # 復路航空券を検索（往路の翌日以降）
                return_date = today + timedelta(days=template['stay_duration'])
                return_flights = Air.objects.filter(
                    place_from=template['return_route'][0],
                    place_to=template['return_route'][1],
                    departure_time__date=return_date
                ).first()
                
                # 宿泊施設を検索
                accommodation = Accommodations.objects.filter(
                    location__icontains=template['accommodation_location']
                ).first()
                
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
