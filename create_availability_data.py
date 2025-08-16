#!/usr/bin/env python
"""
空き状況の初期データを作成するスクリプト
"""
import os
import sys
import django
from datetime import date, timedelta

# Django設定
sys.path.append('/Users/iniad/bookiniad.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.settings')
django.setup()

from main.models import Accommodations, Air, AccommodationAvailability, FlightAvailability


def create_accommodation_availability():
    """宿泊施設の空き状況データを作成"""
    print("宿泊施設の空き状況データを作成中...")
    
    accommodations = Accommodations.objects.all()
    start_date = date.today()
    end_date = start_date + timedelta(days=365)  # 1年間のデータ
    
    current_date = start_date
    while current_date <= end_date:
        for accommodation in accommodations:
            # 基本的に総部屋数の80%を空室として設定
            available_rooms = int(accommodation.total_rooms * 0.8)
            
            # 週末や特定の日は空室を少なくする
            if current_date.weekday() in [4, 5]:  # 金曜日、土曜日
                available_rooms = int(accommodation.total_rooms * 0.3)
            
            AccommodationAvailability.objects.get_or_create(
                accommodation=accommodation,
                date=current_date,
                defaults={'available_rooms': available_rooms}
            )
        
        current_date += timedelta(days=1)
    
    print(f"宿泊施設の空き状況データ作成完了: {len(accommodations)}施設 x 365日")


def create_flight_availability():
    """航空券の空き状況データを作成"""
    print("航空券の空き状況データを作成中...")
    
    flights = Air.objects.all()
    start_date = date.today()
    end_date = start_date + timedelta(days=365)  # 1年間のデータ
    
    current_date = start_date
    while current_date <= end_date:
        for flight in flights:
            # 基本的に総座席数の70%を空席として設定
            available_seats = int(flight.available_seats * 0.7)
            
            # 週末や特定の日は空席を少なくする
            if current_date.weekday() in [4, 5]:  # 金曜日、土曜日
                available_seats = int(flight.available_seats * 0.4)
            
            FlightAvailability.objects.get_or_create(
                flight=flight,
                date=current_date,
                defaults={'available_seats': available_seats}
            )
        
        current_date += timedelta(days=1)
    
    print(f"航空券の空き状況データ作成完了: {len(flights)}便 x 365日")


if __name__ == '__main__':
    print("空き状況データの作成を開始します...")
    create_accommodation_availability()
    create_flight_availability()
    print("すべての空き状況データ作成が完了しました！")
