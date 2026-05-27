from android.service import AndroidService
from android import api_version
from jnius import autoclass, cast
import time
import requests
import re
import json
from datetime import datetime

class MonitorService(AndroidService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.session = None
        self.last_orders = set()
        self.account_id = ""
        self.username = ""
        self.password = ""
        
    def onStartCommand(self, intent, flags, startId):
        self.running = True
        
        if intent:
            self.username = intent.getStringExtra("username", "")
            self.password = intent.getStringExtra("password", "")
            self.account_id = intent.getStringExtra("account_id", "")
        
        self.start_monitoring()
        return self.START_STICKY
    
    def start_monitoring(self):
        def monitor_loop():
            while self.running:
                try:
                    if not self.session:
                        self.login()
                    
                    if self.session:
                        self.check_orders()
                except Exception as e:
                    pass
                
                time.sleep(5)
        
        from threading import Thread
        Thread(target=monitor_loop, daemon=True).start()
    
    def login(self):
        try:
            self.session = requests.Session()
            response = self.session.post(
                'https://order.zrygame.com/gm/login',
                data={'username': self.username, 'password': self.password},
                timeout=15
            )
            if '登录成功' not in response.text:
                self.session = None
        except:
            self.session = None
    
    def check_orders(self):
        try:
            page = 1
            while True:
                response = self.session.get(f'https://order.zrygame.com/gm/orders?page={page}', timeout=15)
                html = response.text
                
                pattern = re.compile(r'<tr[^>]*>.*?</tr>', re.DOTALL)
                rows = pattern.findall(html)
                
                if not rows:
                    break
                
                for row in rows:
                    order_id = re.search(r'BR\d{14,}', row)
                    amount = re.search(r'<td[^>]*>¥([\d.]+)</td>', row)
                    pay_type = re.search(r'(微信|支付宝)', row)
                    
                    if order_id and amount:
                        order_id_str = order_id.group(0)
                        if order_id_str not in self.last_orders:
                            self.last_orders.add(order_id_str)
                            self.speak(f"{self.account_id} 发现新订单 {pay_type.group(1) if pay_type else '其他'}充值 {amount.group(1)}元")
                            self.show_notification(order_id_str, amount.group(1))
                
                page += 1
        except:
            pass
    
    def speak(self, message):
        try:
            TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            
            tts = TextToSpeech(PythonActivity.mActivity, None)
            tts.speak(message, TextToSpeech.QUEUE_FLUSH, None, None)
        except:
            pass
    
    def show_notification(self, order_id, amount):
        try:
            Context = autoclass('android.content.Context')
            NotificationManager = autoclass('android.app.NotificationManager')
            NotificationChannel = autoclass('android.app.NotificationChannel')
            Notification = autoclass('android.app.Notification')
            
            channel_id = "order_monitor_channel"
            channel_name = "订单监控"
            channel_desc = "新订单通知"
            
            notification_manager = cast('android.app.NotificationManager', 
                PythonActivity.mActivity.getSystemService(Context.NOTIFICATION_SERVICE))
            
            if api_version >= 26:
                channel = NotificationChannel(channel_id, channel_name, NotificationManager.IMPORTANCE_HIGH)
                channel.setDescription(channel_desc)
                notification_manager.createNotificationChannel(channel)
            
            builder = autoclass('android.app.Notification$Builder')(PythonActivity.mActivity, channel_id)
            builder.setContentTitle(f"{self.account_id} 新订单")
            builder.setContentText(f"订单号: {order_id}\n金额: ¥{amount}")
            builder.setSmallIcon(autoclass('android.R$drawable').ic_dialog_info)
            builder.setAutoCancel(True)
            
            notification = builder.build()
            notification_manager.notify(1, notification)
        except:
            pass
    
    def onDestroy(self):
        self.running = False
        super().onDestroy()

if __name__ == '__main__':
    MonitorService().main()