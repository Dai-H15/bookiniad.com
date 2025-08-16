from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import date, timedelta
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
            
            # 航空券データを読み込み
            self.stdout.write('航空券データを読み込み中...')
            call_command('loaddata', 'main/fixtures/air.json')
            self.stdout.write(f'  ✓ 航空券データを読み込みました: {Air.objects.count()}件')
            
            # 旅行パッケージデータを読み込み
            self.stdout.write('旅行パッケージデータを読み込み中...')
            call_command('loaddata', 'main/fixtures/travel_packages.json')
            self.stdout.write(f'  ✓ 旅行パッケージデータを読み込みました: {TravelPackage.objects.count()}件')
            
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
        self.stdout.write('航空券の空き状況データを作成中...')
        flights = Air.objects.all()
        
        flight_count = 0
        for i in range(days):
            current_date = start_date + timedelta(days=i)
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
        
        self.stdout.write(f'  ✓ 航空券の空き状況データ: {flight_count}件')
