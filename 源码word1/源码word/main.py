# -*- coding: utf-8 -*-
# ESP32 智能温室

from machine import Pin, PWM, I2C, ADC
from time import sleep_ms
from simple import MQTTClient
from hcsr04 import HCSR04
import network
import json
import ssd1306
import dht
import gc
import neopixel

gc.collect()

# ==================== 硬件初始化 ====================

# 蜂鸣器 GPIO0
BUZZER_PIN = 0
buzzer = PWM(Pin(BUZZER_PIN), freq=1000, duty=0)

# GPIO16 LED
led16 = Pin(16, Pin.OUT)
led16.value(0)

# K2 GPIO25：OLED页面切换
key_screen = Pin(25, Pin.IN, Pin.PULL_UP)

# K3 GPIO26：自动/手动模式
key_mode = Pin(26, Pin.IN, Pin.PULL_UP)

# K4 GPIO4：手动模式控制LED
key_led = Pin(4, Pin.IN, Pin.PULL_UP)

# DHT11 GPIO32
dht_sensor = dht.DHT11(Pin(32))

# OLED
i2c = I2C(
    scl=Pin(14),
    sda=Pin(13),
    freq=100000
)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# HC-SR04
ultra = HCSR04(
    trigger_pin=33,
    echo_pin=27
)

# 光敏电阻 GPIO34
light_adc = ADC(Pin(34))
light_adc.atten(ADC.ATTN_11DB)

# NeoPixel GPIO15
NUM_PIX = 4
strip = neopixel.NeoPixel(
    Pin(15),
    NUM_PIX
)

# ==================== 参数 ====================

TEMP_MAX = 30
TEMP_MIN = 18

HUM_MAX = 75
HUM_MIN = 40

DIST_ALARM_CM = 15

# 暗约780，亮4095
LIGHT_THRESHOLD = 2000

# True = 自动
# False = 手动
AUTO_MODE = True

# 手动模式LED状态
# True = 亮
# False = 灭
MANUAL_LED_CONTROL = False

# OLED页面
# 0 = 传感器页面
# 1 = 连接状态页面
screen_page = 0

# ==================== 状态变量 ====================

temp_ = 0
hum_ = 0
dist_ = 999.0
light_ = 0

# WiFi状态
wifi_connected = False

# OneNET状态
cloud_connected = False

# MQTT是否可用
mqtt_available = False

# MQTT客户端
client = None

# 离线重连计数
offline_counter = 0

# ==================== RGB ====================

def set_rgb(color):
    for i in range(NUM_PIX):
        strip[i] = color
    strip.write()

# ==================== LED ====================

def set_led(state):
    led16.value(1 if state else 0)

# ==================== 蜂鸣器 ====================

def beep(t_ms, freq=800):
    buzzer.freq(freq)
    buzzer.duty(512)
    sleep_ms(t_ms)
    buzzer.duty(0)

def alarm_beep():
    beep(200, 800)
    sleep_ms(100)
    beep(200, 600)

# ==================== 光敏 ====================

def read_light():
    return light_adc.read()

# ==================== DHT11 ====================

def get_dht11():
    global temp_, hum_

    try:
        dht_sensor.measure()
        temp_ = dht_sensor.temperature()
        hum_ = dht_sensor.humidity()

        print("Temp:", temp_, "C")
        print("Hum :", hum_, "%")

    except Exception as e:
        print("DHT11 error:", e)
        temp_ = -1
        hum_ = -1

# ==================== 超声波 ====================

def get_ultrasonic():
    global dist_

    try:
        distance = ultra.distance_cm()

        if distance < 0:
            distance = 999.0

        dist_ = round(distance, 1)

        print("Dist:", dist_, "cm")

    except Exception as e:
        print("Ultrasonic error:", e)
        dist_ = 999.0

# ==================== WiFi状态 ====================

def check_wifi():
    global wifi_connected

    try:
        wlan = network.WLAN(network.STA_IF)
        wifi_connected = wlan.isconnected()

    except Exception as e:
        print("WiFi check error:", e)
        wifi_connected = False

    return wifi_connected

# ==================== OLED ====================

def oled_show():
    oled.fill(0)

    # ---------- 第一页：传感器 ----------
    if screen_page == 0:

        oled.text(
            "Smart GreenHouse",
            0,
            0
        )

        oled.text(
            "T:{}C H:{}%".format(
                temp_,
                hum_
            ),
            0,
            18
        )

        oled.text(
            "Light:{}".format(
                light_
            ),
            0,
            31
        )

        oled.text(
            "Dist:{}cm".format(
                dist_
            ),
            0,
            44
        )

        if AUTO_MODE:
            oled.text(
                "MODE:AUTO",
                0,
                57
            )
        else:
            oled.text(
                "MODE:MANUAL",
                0,
                57
            )

    # ---------- 第二页：连接状态 ----------
    else:

        oled.text(
            "Smart GreenHouse",
            0,
            0
        )

        if wifi_connected:
            oled.text(
                "WiFi:OK",
                0,
                18
            )
        else:
            oled.text(
                "WiFi:ERROR",
                0,
                18
            )

        if cloud_connected:
            oled.text(
                "OneNET:OK",
                0,
                31
            )
        else:
            oled.text(
                "OneNET:ERROR",
                0,
                31
            )

        if led16.value():
            oled.text(
                "LED:ON",
                0,
                44
            )
        else:
            oled.text(
                "LED:OFF",
                0,
                44
            )

        if AUTO_MODE:
            oled.text(
                "MODE:AUTO",
                0,
                57
            )
        else:
            oled.text(
                "MODE:MANUAL",
                0,
                57
            )

    oled.show()

# ==================== 按键 ====================

def check_keys():
    global AUTO_MODE
    global MANUAL_LED_CONTROL
    global screen_page

    # ---------- K2：切换OLED页面 ----------

    if key_screen.value() == 0:

        sleep_ms(20)

        if key_screen.value() == 0:

            screen_page = 1 - screen_page

            print(
                "K2 -> Screen:",
                screen_page
            )

            check_wifi()
            oled_show()

            while key_screen.value() == 0:
                sleep_ms(10)

    # ---------- K3：自动/手动 ----------

    if key_mode.value() == 0:

        sleep_ms(20)

        if key_mode.value() == 0:

            AUTO_MODE = not AUTO_MODE

            if AUTO_MODE:

                print(
                    "K3 -> AUTO MODE"
                )

                if light_ < LIGHT_THRESHOLD:
                    set_led(True)
                else:
                    set_led(False)

            else:

                print(
                    "K3 -> MANUAL MODE"
                )

                set_led(
                    MANUAL_LED_CONTROL
                )

            oled_show()

            while key_mode.value() == 0:
                sleep_ms(10)

    # ---------- K4：手动控制LED ----------

    if key_led.value() == 0:

        sleep_ms(20)

        if key_led.value() == 0:

            if not AUTO_MODE:

                MANUAL_LED_CONTROL = not MANUAL_LED_CONTROL

                set_led(
                    MANUAL_LED_CONTROL
                )

                print(
                    "K4 -> LED:",
                    MANUAL_LED_CONTROL
                )

            else:

                print(
                    "K4 ignored: AUTO MODE"
                )

            oled_show()

            while key_led.value() == 0:
                sleep_ms(10)

# ==================== 报警和LED控制 ====================

def check_alarm():

    alarm_flag = False

    # ---------- 温度异常 ----------

    if temp_ < TEMP_MIN or temp_ > TEMP_MAX:

        alarm_flag = True

        print(
            "WARNING: Temperature abnormal!"
        )

    # ---------- 湿度异常 ----------

    if hum_ < HUM_MIN or hum_ > HUM_MAX:

        alarm_flag = True

        print(
            "WARNING: Humidity abnormal!"
        )

    # ---------- 距离过近 ----------

    if dist_ < DIST_ALARM_CM:

        alarm_flag = True

        print(
            "WARNING: Object too close!"
        )

    # ---------- 异常报警 ----------

    if alarm_flag:

        set_rgb(
            (40, 0, 0)
        )

        set_led(False)

        alarm_beep()

        print(
            "SYSTEM ALARM"
        )

        return

    # ---------- 自动模式 ----------

    if AUTO_MODE:

        if light_ < LIGHT_THRESHOLD:

            set_led(True)

            set_rgb(
                (40, 40, 0)
            )

            print(
                "AUTO: Light insufficient -> LED ON"
            )

        else:

            set_led(False)

            set_rgb(
                (0, 40, 0)
            )

            print(
                "AUTO: Light sufficient -> LED OFF"
            )

    # ---------- 手动模式 ----------

    else:

        set_led(
            MANUAL_LED_CONTROL
        )

        set_rgb(
            (0, 40, 0)
        )

        print(
            "MANUAL: LED =",
            MANUAL_LED_CONTROL
        )

# ==================== OneNET ====================

# 这里保持你原来成功的参数
SERVER = 'mqtts.heclouds.com'
PORT = 1883
NAME = '2Z8hj8HSP4'
CLIENT_ID = "202312902216"

# 把你原来能够成功连接的Token放这里
PSWD = 'version=2018-10-31&res=products%2F2Z8hj8HSP4%2Fdevices%2F202312902216&et=1790843847&method=md5&sign=oDVolJH5QdHQCpAX8b5kfg%3D%3D'

publish_Topic = '$sys/2Z8hj8HSP4/202312902216/thing/property/post'
post_Topic = '$sys/2Z8hj8HSP4/202312902216/thing/property/post/reply'
subscribe_Topic = '$sys/2Z8hj8HSP4/202312902216/thing/property/set'
respose_Topic = '$sys/2Z8hj8HSP4/202312902216/thing/property/set_reply'

# ==================== MQTT回调 ====================

def MQTT_callback(topic, msg):

    global AUTO_MODE
    global MANUAL_LED_CONTROL
    global cloud_connected

    print("topic:", topic)
    print("msg:", msg)

    try:

        json_str = msg.decode('utf-8')
        dic_msg = json.loads(json_str)

        # ====================
        # OneNET上报回复
        # ====================

        if topic == post_Topic.encode():

            if dic_msg.get("code") == 200:

                cloud_connected = True

                print(
                    "OneNET upload success"
                )

            else:

                print(
                    "OneNET upload failed"
                )

                print(dic_msg)

            return

        # ====================
        # OneNET下发命令
        # ====================

        cloud_connected = True

        print(
            "Received command:",
            dic_msg
        )

        # ====================
        # 回复OneNET
        # ====================

        if "id" in dic_msg:

            msg_id = dic_msg["id"]

            res_msg_dic = {
                "id": msg_id,
                "code": 200,
                "msg": "success"
            }

            res_msg_json = json.dumps(
                res_msg_dic
            )

            try:

                client.publish(
                    topic=respose_Topic,
                    msg=res_msg_json,
                    retain=False,
                    qos=0
                )

            except Exception as e:

                print(
                    "Reply error:",
                    e
                )

        if "params" not in dic_msg:
            return

        params = dic_msg["params"]

        # ====================
        # led_mode
        # true = 自动
        # false = 手动
        # ====================

        if "led_mode" in params:

            mode_value = bool(
                params["led_mode"]
            )

            AUTO_MODE = mode_value

            print(
                "Cloud led_mode =",
                AUTO_MODE
            )

            if AUTO_MODE:

                print(
                    "Cloud -> AUTO MODE"
                )

                if light_ < LIGHT_THRESHOLD:
                    set_led(True)
                else:
                    set_led(False)

            else:

                print(
                    "Cloud -> MANUAL MODE"
                )

                set_led(
                    MANUAL_LED_CONTROL
                )

        # ====================
        # led16_control
        # true = LED亮
        # false = LED灭
        # ====================

        if "led16_control" in params:

            control_value = bool(
                params["led16_control"]
            )

            MANUAL_LED_CONTROL = control_value

            print(
                "Cloud LED control =",
                MANUAL_LED_CONTROL
            )

            if not AUTO_MODE:

                set_led(
                    MANUAL_LED_CONTROL
                )

            else:

                print(
                    "LED control ignored: AUTO MODE"
                )

        check_wifi()
        oled_show()

    except Exception as e:

        print(
            "MQTT callback error:",
            e
        )

# ==================== 上传OneNET ====================

def MQTT_send():

    global light_
    global cloud_connected
    global mqtt_available

    # ====================
    # 本地传感器
    # ====================

    get_dht11()
    get_ultrasonic()

    light_ = read_light()

    print(
        "Light:",
        light_
    )

    # ====================
    # 本地控制
    # ====================

    check_alarm()

    # ====================
    # WiFi状态
    # ====================

    check_wifi()

    # ====================
    # OLED
    # ====================

    oled_show()

    # ====================
    # 离线模式
    # ====================

    if not mqtt_available:

        print(
            "OFFLINE: skip OneNET upload"
        )

        return

    # ====================
    # 数据类型处理
    # ====================

    try:
        t = float(temp_)
    except:
        t = 0

    try:
        h = int(hum_)
    except:
        h = 0

    try:
        dist = float(dist_)
    except:
        dist = 999.0

    try:
        light = int(light_)
    except:
        light = 0

    # ====================
    # OneNET数据
    # ====================

    mymessage = {

        "id": "123",

        "version": "1.0",

        "params": {

            "temp_value": {
                "value": t
            },

            "humidity_value": {
                "value": h
            },

            "ultrasonic_dist": {
                "value": dist
            },

            "light_value": {
                "value": light
            },

            "led16_status": {
                "value": bool(
                    led16.value()
                )
            },

            "led_mode": {
                "value": bool(
                    AUTO_MODE
                )
            }
        }
    }

    msg_json = json.dumps(
        mymessage
    )

    print()
    print("--------------------------------")
    print("Send to OneNET:")
    print(msg_json)
    print("--------------------------------")

    # ====================
    # 上传
    # ====================

    try:

        client.publish(
            topic=publish_Topic,
            msg=msg_json
        )

        cloud_connected = True

        print(
            "Upload OK"
        )

    except Exception as e:

        cloud_connected = False
        mqtt_available = False

        print(
            "Upload error:",
            e
        )

        print(
            "Switch to OFFLINE MODE"
        )

        try:

            client.disconnect()

        except:

            pass

# ==================== MQTT客户端 ====================

# 这里不改变你原来的MQTT连接方式

client = MQTTClient(
    CLIENT_ID,
    SERVER,
    PORT,
    NAME,
    PSWD,
    60
)

print()
print("==============================")
print(" Smart GreenHouse Start")
print("==============================")

print(
    "start connect..."
)

client.set_callback(
    MQTT_callback
)

# ====================
# 首次连接
# ====================

try:

    client.connect()

    cloud_connected = True
    mqtt_available = True

    print(
        "success connect!"
    )

except Exception as e:

    cloud_connected = False
    mqtt_available = False

    print(
        "OneNET connect error:",
        e
    )

    print(
        "OFFLINE MODE"
    )

# ====================
# 只有连接成功才订阅
# ====================

if mqtt_available:

    try:

        client.subscribe(
            post_Topic
        )

        client.subscribe(
            subscribe_Topic
        )

        print(
            "MQTT subscribe success"
        )

    except Exception as e:

        print(
            "MQTT subscribe error:",
            e
        )

        cloud_connected = False
        mqtt_available = False

# ====================
# OLED初始显示
# ====================

check_wifi()
oled_show()

# ==================== 主循环 ====================

try:

    while True:

        # ====================
        # 检查WiFi
        # ====================

        check_wifi()

        # ====================
        # 检查云端消息
        # ====================

        if mqtt_available:

            try:

                client.check_msg()

            except Exception as e:

                print(
                    "MQTT check error:",
                    e
                )

                cloud_connected = False
                mqtt_available = False

                print(
                    "MQTT disconnected -> OFFLINE MODE"
                )

                try:
                    client.disconnect()
                except:
                    pass

        # ====================
        # 检查K2/K3/K4
        # ====================

        check_keys()

        # ====================
        # 读取传感器
        # 本地控制
        # OLED
        # 上传
        # ====================

        MQTT_send()

        # ====================
        # 100ms检查一次
        # ====================

        for i in range(20):

            # WiFi

            check_wifi()

            # MQTT

            if mqtt_available:

                try:

                    client.check_msg()

                except Exception as e:

                    print(
                        "MQTT check error:",
                        e
                    )

                    cloud_connected = False
                    mqtt_available = False

                    print(
                        "MQTT disconnected -> OFFLINE MODE"
                    )

                    try:
                        client.disconnect()
                    except:
                        pass

            # 按键

            check_keys()

            sleep_ms(100)

        # ====================
        # 离线重新连接
        # ====================

        if not mqtt_available:

            offline_counter += 1

            # 主循环大约2秒一次
            # 5次约10秒

            if offline_counter >= 5:

                print()
                print(
                    "Try reconnect..."
                )

                check_wifi()

                if wifi_connected:

                    print(
                        "WiFi OK -> retry OneNET"
                    )

                    try:

                        # ====================
                        # 重新创建MQTT客户端
                        # 参数与原代码完全一致
                        # ====================

                        client = MQTTClient(
                            CLIENT_ID,
                            SERVER,
                            PORT,
                            NAME,
                            PSWD,
                            60
                        )

                        client.set_callback(
                            MQTT_callback
                        )

                        client.connect()

                        print(
                            "OneNET reconnect success!"
                        )

                        # 连接成功后订阅

                        client.subscribe(
                            post_Topic
                        )

                        client.subscribe(
                            subscribe_Topic
                        )

                        cloud_connected = True
                        mqtt_available = True

                        print(
                            "MQTT subscribe success"
                        )

                    except Exception as e:

                        cloud_connected = False
                        mqtt_available = False

                        print(
                            "OneNET reconnect error:",
                            e
                        )

                        print(
                            "Still OFFLINE MODE"
                        )

                        try:
                            client.disconnect()
                        except:
                            pass

                else:

                    print(
                        "WiFi still unavailable"
                    )

                offline_counter = 0

        else:

            offline_counter = 0

except KeyboardInterrupt:

    print(
        "Program stopped"
    )

finally:

    # ====================
    # 关闭蜂鸣器
    # ====================

    buzzer.duty(0)
    buzzer.deinit()

    # ====================
    # LED关闭
    # ====================

    led16.value(0)

    # ====================
    # RGB关闭
    # ====================

    set_rgb(
        (0, 0, 0)
    )

    # ====================
    # OLED关闭
    # ====================

    oled.fill(0)
    oled.show()

    # ====================
    # MQTT断开
    # ====================

    try:

        if client is not None:
            client.disconnect()

    except:

        pass

    print(
        "外设已关闭"
    )