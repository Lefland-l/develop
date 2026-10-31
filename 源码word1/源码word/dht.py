# -*- coding: utf-8 -*-
# 说明: DTH11温湿度传感器, 获取温湿度, 并显示在OLED显示屏上
# author: Clark
# 2022-10-12

import time
from machine import Pin, I2C
import ssd1306  #需要在设备同目录下, 创建ssd1306.py程序, 具体代码参见ssd1306相关章节
import dht      #dht库, 包含DTH11温湿度传感器的常用驱动函数

#设置温湿度传感器, 数据针接到GP33口
d = dht.DHT11(Pin(32))
#设置SSD1306液晶屏, 数据针接GP13和GP14号
i2c = I2C(scl=Pin(14), sda=Pin(13), freq=100000)  #Init i2c
lcd = ssd1306.SSD1306_I2C(128,64,i2c)             #创建ssd1306对象, 以调用相关功能函数

i=1
while True:
    d.measure()                 # 调用DHT类库中测量数据的函数
    temp_ = str(d.temperature()) #读取measure()函数中的温度数据
    hum_ = str(d.humidity())     # 读取measure()函数中的湿度数据

    #在电脑屏幕底部shell打印输出
    print("第"+str(i)+"次检测...")
    print('Temp:'+ temp_+"C")
    print('Hum:'+ hum_+"%")

    #在SSD1306屏幕上输出
    lcd.fill(0)  #先清理屏幕
    lcd.text("Form DHT11",24,8)
    lcd.text("Temp: "+temp_ +"C",24,16)     #在指定坐标显示温度
    lcd.text(" Hum: "+hum_ +"%",24,30)      #在指定坐标显示湿度
    lcd.text("Count: " + str(i) ,24,56)     #在指定坐标显示统计次数
    lcd.show()  #到屏幕上显示

    i=i+1   #统计次数加1
    time.sleep(5)