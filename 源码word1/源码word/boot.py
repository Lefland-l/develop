# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()

# -*- coding: utf-8 -*-
# Author: Clark
# 说明：boot.py是ESP32上电时首先自动运行的代码文件,
# 通过WiFi接入热点，以提供连接Intnet的能力。
# 加入GP22板载LED等闪烁功能，连上WiFi长亮，否则长灭。注意on/off颠倒
# 日期：2025-9-13
# ---------------------------------------
from machine import Pin, I2C
import gc                              #内存回收
gc.collect()

#引用模块
import network
import time

# led 22口，板载,同时通过扩展板引到右下角流水灯D8
led = Pin(22,Pin.OUT)                      #16口的LED，用在远程控制

#建立WiFi连接
def wifi_conn():
    ssid_c='winrt'                       #要接入热点的SSID和密码
    password = '20055002'
    
    #LED闪烁，开始连接WiFi
    led.off()
    time.sleep_ms(300)
    led.on()
    time.sleep_ms(300)
    
    wlan = network.WLAN(network.STA_IF)   # 创建STA模式
    wlan.active(True)                     # 激活
        
    # 检测是否已经连接WiFi
    count=0                               #尝试连接10次
    if wlan.isconnected():
        led.off()
        print('\033[31m当前esp32已连接WiFi，ip地址：%s \033[0m'%(wlan.ifconfig()[0]))
    else:
        # 搜索WiFi
        print('搜索WiFi信号...')
        ssid_all = wlan.scan()     # 扫描附近的WiFi接入点，扫描的时候 定时器无法执行

        get_ssid = 0
        for ssid in ssid_all:
            #print('%s\n'%str(bytes.decode(ssid[0])))
            if ssid_c == bytes.decode(ssid[0]):
                get_ssid = 1
        if get_ssid == 1:
            print('找到热点，准备连接。')
            # 连接WiFi
            try:
                wlan.connect(ssid_c,password)   # WiFi名，密码
                print('正在连接...',end="")                
                while not wlan.isconnected() and count<10:  
                    print('.',end="")
                    time.sleep(1)
                    count += 1                
            except:
                led.on()
                print('WiFi连接异常，请检查配置')
                sys.exit(-1)
            else:
                led.off()
                print('\033[31m 已连接，WiFi名：%s IP地址：%s \033[0m'%(ssid_c,wlan.ifconfig()[0]))
        else:
            led.on()
            print('找不到WiFi热点,请检查热点是否开启。')

wifi_conn()

