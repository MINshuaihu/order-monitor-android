[app]

title = 元宝玄武订单监控
package.name = ordermonitor
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1.0

requirements = python3,kivy,requests,android,jnius
android.api = 33
android.ndk = 25b
android.sdk = 24

android.permissions = INTERNET,WAKE_LOCK,ACCESS_NETWORK_STATE
android.add_assets = service/
android.add_jars = None
android.add_src = None
android.add_libs = None

android.meta_data = None
android.presplash_color = #FFFFFF
android.presplash_drawable = None
android.icon = None
android.launcher_icon = None

android.build_dir = ./build
android.app_dir = ./bin

android.enable_audio = True

[buildozer]
log_level = 2
warn_on_root = 1
android.accept_sdk_license = True