import kivy
kivy.require('2.3.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.utils import platform
from kivy.properties import StringProperty, NumericProperty

import requests
import re
import json
import time
import os
from datetime import datetime
from threading import Thread

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from jnius import autoclass

class VoiceManager:
    def __init__(self):
        self.enabled = True
    
    def speak(self, message):
        if not self.enabled:
            return
        
        if platform == 'android':
            try:
                TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                
                tts = TextToSpeech(PythonActivity.mActivity, None)
                tts.speak(message, TextToSpeech.QUEUE_FLUSH, None, None)
            except:
                pass
        else:
            try:
                import winsound
                winsound.Beep(1000, 500)
            except:
                pass

class OrderMonitor:
    def __init__(self, account_id, callback):
        self.account_id = account_id
        self.callback = callback
        self.session = requests.Session()
        self.running = False
        self.last_orders = set()
        self.voice_manager = VoiceManager()
        
    def login(self, username, password):
        try:
            response = self.session.post(
                'https://order.zrygame.com/gm/login',
                data={'username': username, 'password': password},
                timeout=15
            )
            return response.ok and '登录成功' in response.text
        except:
            return False
    
    def get_dashboard_data(self):
        try:
            response = self.session.get('https://order.zrygame.com/gm/', timeout=15)
            html = response.text
            
            today_orders = re.search(r'今日订单[\s\S]*?(\d+)', html)
            today_amount = re.search(r'今日金额[\s\S]*?¥([\d.]+)', html)
            unsettled = re.search(r'未结算[\s\S]*?¥([\d.]+)', html)
            
            return {
                'today_orders': int(today_orders.group(1)) if today_orders else 0,
                'today_amount': float(today_amount.group(1)) if today_amount else 0.0,
                'unsettled': float(unsettled.group(1)) if unsettled else 0.0
            }
        except:
            return {'today_orders': 0, 'today_amount': 0.0, 'unsettled': 0.0}
    
    def get_orders(self, page=1):
        try:
            response = self.session.get(f'https://order.zrygame.com/gm/orders?page={page}', timeout=15)
            return response.text
        except:
            return ''
    
    def parse_orders(self, html):
        orders = []
        pattern = re.compile(r'<tr[^>]*>.*?</tr>', re.DOTALL)
        rows = pattern.findall(html)
        
        for row in rows:
            order_id = re.search(r'BR\d{14,}', row)
            amount = re.search(r'<td[^>]*>¥([\d.]+)</td>', row)
            pay_type = re.search(r'(微信|支付宝)', row)
            
            if order_id and amount:
                orders.append({
                    'order_id': order_id.group(0),
                    'amount': float(amount.group(1)),
                    'pay_type': pay_type.group(1) if pay_type else '其他'
                })
        return orders
    
    def start(self, username, password):
        if not self.login(username, password):
            return False
        
        self.running = True
        Thread(target=self.monitor_loop, daemon=True).start()
        return True
    
    def stop(self):
        self.running = False
    
    def monitor_loop(self):
        while self.running:
            try:
                data = self.get_dashboard_data()
                self.callback(self.account_id, 'stats', data)
                
                page = 1
                all_orders = []
                
                while True:
                    html = self.get_orders(page)
                    orders = self.parse_orders(html)
                    if not orders:
                        break
                    all_orders.extend(orders)
                    page += 1
                
                for order in all_orders:
                    if order['order_id'] not in self.last_orders:
                        self.last_orders.add(order['order_id'])
                        self.callback(self.account_id, 'new_order', order)
                        self.voice_manager.speak(f"{self.account_id} 发现新订单 {order['pay_type']}充值 {order['amount']}元")
                
            except Exception as e:
                pass
            
            time.sleep(5)

class AccountTab(BoxLayout):
    account_id = StringProperty('')
    today_orders = NumericProperty(0)
    today_amount = StringProperty('¥0.00')
    unsettled = StringProperty('¥0.00')
    
    def __init__(self, account_id, username, password, **kwargs):
        super().__init__(**kwargs)
        self.account_id = account_id
        self.username = username
        self.password = password
        self.monitor = None
        self.build_ui()
    
    def build_ui(self):
        self.orientation = 'vertical'
        
        header = GridLayout(cols=2, size_hint_y=0.15)
        header.add_widget(Label(text=f'账号: {self.account_id}', bold=True, font_size=18))
        header.add_widget(Label(text='', size_hint_x=0.3))
        self.add_widget(header)
        
        stats = GridLayout(cols=2, size_hint_y=0.25)
        stats.add_widget(Label(text='今日订单:', font_size=16))
        self.order_count = Label(text=str(self.today_orders), font_size=20, color=(0, 1, 0, 1))
        stats.add_widget(self.order_count)
        
        stats.add_widget(Label(text='今日金额:', font_size=16))
        self.today_label = Label(text=self.today_amount, font_size=20, color=(0, 1, 0, 1))
        stats.add_widget(self.today_label)
        
        stats.add_widget(Label(text='未结算:', font_size=16))
        self.unsettled_label = Label(text=self.unsettled, font_size=20, color=(1, 0, 0, 1))
        stats.add_widget(self.unsettled_label)
        self.add_widget(stats)
        
        self.log_scroll = ScrollView(size_hint_y=0.45)
        self.log_label = Label(text='', size_hint_y=None, font_size=14)
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        self.log_scroll.add_widget(self.log_label)
        self.add_widget(self.log_scroll)
        
        self.start_btn = Button(text='启动监控', size_hint_y=0.15, font_size=18, background_color=(0, 1, 0, 1))
        self.start_btn.bind(on_press=self.start_monitor)
        self.add_widget(self.start_btn)
    
    def add_log(self, text):
        now = datetime.now().strftime('%H:%M:%S')
        self.log_label.text += f'[{now}] {text}\n'
    
    def update_stats(self, data):
        self.today_orders = data['today_orders']
        self.today_amount = f"¥{data['today_amount']:.2f}"
        self.unsettled = f"¥{data['unsettled']:.2f}"
        self.order_count.text = str(self.today_orders)
        self.today_label.text = self.today_amount
        self.unsettled_label.text = self.unsettled
        self.add_log(f"今日订单: {data['today_orders']} 条, 金额: ¥{data['today_amount']:.2f}")
    
    def handle_new_order(self, order):
        self.add_log(f"新订单: {order['pay_type']} ¥{order['amount']:.2f}")
    
    def start_monitor(self, instance):
        if self.monitor is None:
            self.monitor = OrderMonitor(self.account_id, self.on_monitor_callback)
        
        if self.monitor.start(self.username, self.password):
            self.start_btn.text = '监控中...'
            self.start_btn.disabled = True
            self.start_btn.background_color = (0.5, 0.5, 0.5, 1)
            self.add_log('监控已启动')
        else:
            self.add_log('登录失败，请检查账号密码')
    
    def on_monitor_callback(self, account_id, type, data):
        if type == 'stats':
            Clock.schedule_once(lambda dt: self.update_stats(data))
        elif type == 'new_order':
            Clock.schedule_once(lambda dt: self.handle_new_order(data))

class LoginScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = 'vertical'
        self.padding = 30
        self.spacing = 20
        
        self.add_widget(Label(text='元宝玄武订单监控', font_size=28, bold=True, size_hint_y=0.15))
        
        self.username_input = TextInput(hint_text='账号', font_size=20, size_hint_y=0.12)
        self.add_widget(self.username_input)
        
        self.password_input = TextInput(hint_text='密码', password=True, font_size=20, size_hint_y=0.12)
        self.add_widget(self.password_input)
        
        self.account_id_input = TextInput(hint_text='账号标识（如：永恒传奇）', font_size=20, size_hint_y=0.12)
        self.add_widget(self.account_id_input)
        
        self.login_btn = Button(text='登录并添加账号', font_size=22, size_hint_y=0.15, background_color=(0, 1, 0, 1))
        self.login_btn.bind(on_press=self.login)
        self.add_widget(self.login_btn)
        
        self.status_label = Label(text='', font_size=18, size_hint_y=0.1, color=(1, 0, 0, 1))
        self.add_widget(self.status_label)
    
    def login(self, instance):
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        account_id = self.account_id_input.text.strip()
        
        if not username or not password or not account_id:
            self.status_label.text = '请填写所有字段'
            return
        
        self.status_label.text = '登录中...'
        
        def do_login():
            session = requests.Session()
            try:
                response = session.post(
                    'https://order.zrygame.com/gm/login',
                    data={'username': username, 'password': password},
                    timeout=15
                )
                
                if '登录成功' in response.text:
                    self.app.add_account(account_id, username, password)
                    self.status_label.text = '登录成功！'
                    self.username_input.text = ''
                    self.password_input.text = ''
                    self.account_id_input.text = ''
                else:
                    self.status_label.text = '登录失败'
            except Exception as e:
                self.status_label.text = f'登录失败: {str(e)}'
        
        Thread(target=do_login, daemon=True).start()

class MonitorApp(App):
    def build(self):
        self.tab_panel = TabbedPanel()
        self.login_screen = LoginScreen(self)
        
        main_tab = TabbedPanelItem(text='登录', font_size=18)
        main_tab.content = self.login_screen
        self.tab_panel.add_widget(main_tab)
        
        self.summary_tab = TabbedPanelItem(text='监控汇总', font_size=18)
        self.summary_content = BoxLayout(orientation='vertical', padding=20)
        self.summary_label = Label(text='暂无数据', font_size=18, size_hint_y=None)
        self.summary_content.add_widget(self.summary_label)
        self.summary_tab.content = self.summary_content
        self.tab_panel.add_widget(self.summary_tab)
        
        self.accounts = {}
        
        if platform == 'android':
            request_permissions([Permission.INTERNET, Permission.WAKE_LOCK])
        
        return self.tab_panel
    
    def add_account(self, account_id, username, password):
        if account_id in self.accounts:
            return
        
        tab = TabbedPanelItem(text=account_id, font_size=18)
        account_tab = AccountTab(account_id, username, password)
        tab.content = account_tab
        self.tab_panel.add_widget(tab)
        self.accounts[account_id] = account_tab
        
        Clock.schedule_once(lambda dt: self.update_summary())
    
    def update_summary(self):
        total_today = 0
        total_unsettled = 0
        total_orders = 0
        
        for acc_id, acc_tab in self.accounts.items():
            total_orders += acc_tab.today_orders
            total_today += float(acc_tab.today_amount.replace('¥', ''))
            total_unsettled += float(acc_tab.unsettled.replace('¥', ''))
        
        summary = f"监控汇总\n\n"
        summary += f"账号数量: {len(self.accounts)}\n"
        summary += f"今日订单: {total_orders} 条\n"
        summary += f"今日金额: ¥{total_today:.2f}\n"
        summary += f"未结算: ¥{total_unsettled:.2f}\n\n"
        
        for acc_id, acc_tab in self.accounts.items():
            summary += f"{acc_id}:\n"
            summary += f"  订单: {acc_tab.today_orders} 条\n"
            summary += f"  金额: {acc_tab.today_amount}\n\n"
        
        self.summary_label.text = summary

if __name__ == '__main__':
    MonitorApp().run()