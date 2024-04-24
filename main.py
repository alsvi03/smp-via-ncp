import redis #  redis-server
import json
import uuid
import datetime

#redis-cli
#keys *
#lrange channel.commands 0 -1

random_uuid = uuid.uuid4() # рандомная генерация ключа

# мгновенное значение, коррекция и установка времени, 30-минутные мощности, 3-х минутки?
# dff

r = redis.Redis(host='localhost', port=6379, db=0)

tBufUART: bytearray = [0] * 40
int_buf: bytearray = [0] * 40

def process_string(input_string):  #приведение ответа к формату буфера
    buffer = []
    for i in range(0, len(input_string), 2):
        if i+1 < len(input_string):
            two_chars = input_string[i:i+2]
            num = two_chars
            buffer.append(num)

    return buffer

def hex_to_int(buff):
    int_buf = [0]*len(buff)
    for i in range(len(buff)):
        int_buf[i]=int(buff[i],16)
    return int_buf

def DecodeDFF(recBuf, shiftInBits): #перевод из dff в int
    i = 0
    result = 0

    while True:
        tmpBuf = recBuf[i] & 0x7F
        tmpRes = tmpBuf << (i * 7)
        result += tmpRes

        if (recBuf[i] & 0x80) > 0:
            i += 1
        else:
            break
    result = result >> shiftInBits

    return result, i + 1





def ncp_checkCRC(buff, size):
    crc = ncp_getCRC(buff, size-3)

    if (crc >> 8) & 0xff == (buff[size-3] ) and (crc & 0xff) == (buff[size-2]):
        return True
    else:
        return False





# Если в данных надо передать байт 0xC0, то применяется механизм байnстаффинга – байт 0xС0
# заменяется последовательностью 0xDB, 0xDC.
# Если в данных надо передать байт 0xDB, то он заменяется последовательностью 0xDB, 0xDD.
def byte_stuffing(buffer):
    stuffed_buffer = [buffer[0]]
    for i in range(1, len(buffer)-1):
        if buffer[i] == 'c0':
            stuffed_buffer.extend(['db', 'dc'])
        elif buffer[i] == 'db':
            stuffed_buffer.extend(['db', 'dd'])
        else:
            stuffed_buffer.append(buffer[i])
    stuffed_buffer.append(buffer[-1])
    return stuffed_buffer


def byte_destuffing(stuffed_buffer):
    destuffed_buffer = [stuffed_buffer[0]]
    i = 1
    while i < len(stuffed_buffer) - 1:
        if stuffed_buffer[i] == 'DB':
            if stuffed_buffer[i + 1] == 'DC':
                destuffed_buffer.append('C0')
                i += 2
            elif stuffed_buffer[i + 1] == 'DD':
                destuffed_buffer.append('DB')
                i += 2
            else:
                destuffed_buffer.append(stuffed_buffer[i])
                i += 1
        else:
            destuffed_buffer.append(stuffed_buffer[i])
            i += 1
    destuffed_buffer.append(stuffed_buffer[-1])
    return destuffed_buffer



def int_to_hex(buff,size,address): # c00677020000000602000100000102000001030000010400000121aac0
    for i in range(size):
            hexval = hex(buff[i])
            hexstr = hexval[2:]
            if len(hexstr) == 1:
                tBufUART[i] = "0" + hexstr
            else:
                tBufUART[i] = hexstr




def add_address():     # добавляем адрес в нужном формате
    hex_address = hex(address)[2:]
    if len(str(abs(address))) == 2:
        int_buf[2] = int(hex_address,16)
    elif len(str(abs(address))) == 3:


        int_buf[2] = int(str(hex_address)[1:],16)
        int_buf[3] = int("0" + str(hex_address)[:1],16)


# def int_to_hex(buff, size,address):
#     hex_str = ""
#     for i in range(size):
#         hexval = hex(buff[i]).replace('0x', '')
#         hex_str += '\\x' + hexval.zfill(2)
#
#     print(hex_str)


def ncp_getCRC(buff, size): # подсчет контрольной суммы
    NCP_CRC_POLYNOM = 0x8005
    crc = 0
    pcBlock = buff


    for i in range(1,size):
        crc ^= pcBlock[i] << 8
        for j in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ NCP_CRC_POLYNOM
            else:
                crc = crc << 1
    return crc

def ncp_addCRC(buff, size): # добавление контрольной суммы в буфер
    crc = ncp_getCRC(buff, size)
    buff[size] = (crc >> 8) & 0xff
    buff[size+1] = crc & 0xff
    return size + 2


def DecToHex_CE318_NCP(buff, address):  # формирование адреса
    for i in range(4):
        buff[i+2] = address[i]
    return

def cut_Buf(buff):  # обрезает нули в конце буфера
    for i in range(len(buff) - 1, -1, -1):
        if buff[i] == 'c0':
            return buff[:i + 1]

    return buff

def create_Packege(address,I1,I2,com):
    # C0 06 77 02 00 00 80 06 02 00      01  A0 F5 94 03   02  10    03   98 CE A7 02   04   B0 05         0C E0 C0

    int_buf[0] = 0xc0
    int_buf[1] = 0x06
    add_address()     #[2-5] - адрес
    int_buf[6] = 0x00  # 0-отправка  80-получение
    int_buf[7] = 0x06  # 6-Данные для устройства 7- ошибка
    int_buf[8] = 0x02  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    int_buf[9] = 0x00  # подкоманда

    if com == 'day': # формирование данных команды
        length = day_Data(int_buf,I1,I2) # length - костыль чтобы потом знать в какие индексы записывать дальнейшие биты
    elif com == 2:
        length = day_Increment(int_buf,I1,I2)
    elif com == 3:
        length = month_Data(int_buf,I1,I2)
    elif com == 4:
        length = month_Increment(int_buf,I1,I2)
    elif com == 5:
        length = charge(address)

    ncp_addCRC(int_buf, length)  # контрольная сумма пакета, 26-27 байты
    int_buf[length+2] = 0xc0 # завершающий бит
    int_to_hex(int_buf, len(int_buf),address) # перевод всего буфера в hex формат
    stuffed_buffer = byte_stuffing(cut_Buf(tBufUART))

    out =""
    for i in range (len(stuffed_buffer)):
        out += stuffed_buffer[i]


    return out





def day_Data(buff,I1,I2):
    buff[10] = 0x01  # 1 команда (запрос Накопление энергии A+ на начало суток)
    buff[11] = 0x00  # Маска, общая энергия (тариф?)
    buff[12] = I1  # номер более поздних суток
    buff[13] = I2  # номер более ранних суток
    buff[14] = 0x02  # 2 команда (запрос Накопление энергии A- на начало суток)
    buff[15] = 0x00  # Маска, общая энергия
    buff[16] = I1  # номер более поздних суток
    buff[17] = I2  # номер более ранних суток
    buff[18] = 0x03  # 3 команда (запрос Накопление энергии R+ на начало суток)
    buff[19] = 0x00  # Маска, общая энергия
    buff[20] = I1  # номер более поздних суток
    buff[21] = I2  # номер более ранних суток
    buff[22] = 0x04  # 4 команда (запрос Накопление энергии R- на начало суток)
    buff[23] = 0x00  # Маска, общая энергия
    buff[24] = I1  # номер более поздних суток
    buff[25] = I2  # номер более ранних суток
    return 26

def day_Increment(buff,I1,I2):
    buff[10] = 0x05  # 5 команда (запрос Накопление энергии A+ за сутки)
    buff[11] = 0x00  # Маска, общая энергия
    buff[12] = I1  # номер более поздних суток
    buff[13] = I2  # номер более ранних суток
    buff[14] = 0x06  # 6 команда (запрос Накопление энергии A- за сутки)
    buff[15] = 0x00  # Маска, общая энергия
    buff[16] = I1  # номер более поздних суток
    buff[17] = I2  # номер более ранних суток
    buff[18] = 0x07  # 7 команда (запрос Накопление энергии R+ за сутки)
    buff[19] = 0x00  # Маска, общая энергия
    buff[20] = I1  # номер более поздних суток
    buff[21] = I2  # номер более ранних суток
    buff[22] = 0x08  # 8 команда (запрос Накопление энергии R- за сутки)
    buff[23] = 0x00  # Маска, общая энергия
    buff[24] = I1  # номер более поздних суток
    buff[25] = I2  # номер более ранних суток
    return 26

    
def month_Data(buff,I1,I2):
    buff[10] = 0x09  # 9 команда (запрос Накопление энергии A+ на начало расчетного периода(месяца))
    buff[11] = 0x00  # Маска, общая энергия
    buff[12] = I1  # номер более позднего месяца
    buff[13] = I2  # номер более раннего месяца
    buff[14] = 0x0A  # 10 команда (запрос Накопление энергии A- на начало расчетного периода(месяца))
    buff[15] = 0x00  # Маска, общая энергия
    buff[16] = I1  # номер более позднего месяца
    buff[17] = I2  # номер более раннего месяца
    buff[18] = 0x0B  # 11 команда (запрос Накопление энергии R+ на начало расчетного периода(месяца))
    buff[19] = 0x00  # Маска, общая энергия
    buff[20] = I1  # номер более позднего месяца
    buff[21] = I2  # номер более раннего месяца
    buff[22] = 0x0C  # 12 команда (запрос Накопление энергии R- на начало расчетного периода(месяца))
    buff[23] = 0x00  # Маска, общая энергия
    buff[24] = I1  # номер более позднего месяца
    buff[25] = I2  # номер более раннего месяца
    return 26
    
def month_Increment(buff,I1,I2):
    buff[10] = 0x0d  # 13 команда (запрос Накопление энергии A+ за расчетный период (месяц))
    buff[11] = 0x00  # Маска, общая энергия
    buff[12] = I1  # номер более позднего месяца
    buff[13] = I2  # номер более раннего месяца
    buff[14] = 0x0e  # 14 команда (запрос Накопление энергии A- за расчетный период (месяц))
    buff[15] = 0x00  # Маска, общая энергия
    buff[16] = I1  # номер более позднего месяца
    buff[17] = I2  # номер более раннего месяца
    buff[18] = 0x0f  # 15 команда (запрос Накопление энергии R+ за расчетный период (месяц))
    buff[19] = 0x00  # Маска, общая энергия
    buff[20] = I1  # номер более позднего месяца
    buff[21] = I2  # номер более раннего месяца
    buff[22] = 0x10  # 16 команда (запрос Накопление энергии R- за расчетный период (месяц))
    buff[23] = 0x00  # Маска, общая энергия
    buff[24] = I1  # номер более позднего месяца
    buff[25] = I2  # номер более раннего месяца
    return 26

def charge(buff):
    int_buf[10] = 0x20  # 32 команда (запрос заряда батареи)
    return 11


def check_ressive_and(answer):




    buff = hex_to_int(byte_destuffing(process_string(answer)))

    if ncp_checkCRC(buff,len(buff)): # проверка целостности пакета
        if buff[7] == 0x07: # обработка ошибки (вместо print должно куда-то возвращаться)
            if buff[8]== 1:
                print ("Ошибка. Используется если в кодах нет адекватной по смыслу ошибки.")
            elif buff[8] == 2:
                print ("Ошибка параметров")
            elif buff[8] == 3:
                print ("Неизвестный/неподдерживаемый код")
            elif buff[8] == 4:
                print ("Ошибка записи")
            elif buff[8] == 5:
                print (" Недостаточно памяти")
            elif buff[8] == 6:
                print ("Неверный адрес")
            elif buff[8] == 7:
                print ("Некоректные данные в команде")
            elif buff[8] == 8:
                print ("Выполняется другая команда или устройство занято")
            elif buff[8] == 9:
                print ("Нет связи")
        elif buff[7] == 0x06:
            if buff[10] == 0x01 : # 1 команда (запрос Накопление энергии A+ на начало суток)
                check_Day_Data(buff)
                json_data = {"ep": check_Day_Data(buff)[0],
                             "em": check_Day_Data(buff)[1],
                             "rp": check_Day_Data(buff)[2],
                             "rm": check_Day_Data(buff)[3],
                             "tarif": 0,
                             "date": datetime.datetime.now().strftime("%d-%m-%Y"),
                             "time":  datetime.datetime.now().strftime("%H:%M:%S"),
                             "poll_date": datetime.datetime.now().strftime("%d-%m-%Y"),
                             "poll_time": datetime.datetime.now().strftime("%H:%M:%S")}



            # elif buff[10] == 0x05: # 5 команда (запрос Накопление энергии A+ за сутки)
            #     check_Day_Increment(buff)
            # elif buff[10] == 0x09: # 9 команда (запрос Накопление энергии A+ на начало расчетного периода(месяца))
            #     check_Month_Data(buff)
            # elif buff[10] == 0x0d:  # 13 команда (запрос Накопление энергии A+ за расчетный период (месяц))
            #     check_Month_Increment(buff)

    else:
        print("Контрольная сумма пакета не совпадает")

    return json_data




def check_Day_Data(buff):
    ep = DecodeDFF(buff[11:25],3)[0]
    i = DecodeDFF(buff[11:25], 3)[1] + 1
    em = DecodeDFF(buff[11+i:25],3)[0]
    i = DecodeDFF(buff[11+i:25], 3)[1] + 1+i
    rp = DecodeDFF(buff[11 + i:25], 3)[0]
    i = DecodeDFF(buff[11+i:25], 3)[1] + 1+i
    rm = DecodeDFF(buff[11 + i:25], 3)[0]

    # print(DecodeDFF(buff[11:25],3)[0])
    # i = DecodeDFF(buff[11:25],3)[1]+1
    # print(DecodeDFF(buff[11+i:25],3)[0])
    # i = DecodeDFF(buff[11+i:25], 3)[1] + 1+i
    # print(DecodeDFF(buff[11 + i:25], 3)[0])
    # i = DecodeDFF(buff[11+i:25], 3)[1] + 1+i
    # print(DecodeDFF(buff[11 + i:25], 3)[0])

    return ep,em,rp,rm



def check_Day_Increment(buff):
    i=0

def check_Month_Data(buff):
    i=0

def check_Month_Increment(buff):
    i=0






#-- создаем пример запроса
json_create_cmd = {
    "channel": 'ktp6',  # название канала
    "cmd": 'day',  # название типа опроса day - показания на начало суток
    "run": 'ce318',  # название вызываемого протокола
    "vm_id": 4,  # id прибора учёта
    "ph": 999,  # адрес под которым счетчик забит в успд
    "trf": '4',  # количество тарифов у счётчика
    "ki": 2,  # коэф тока
    "ku": 3,  # коэф трансформации
    "ago": 1,  # начало опроса 0 - текущий день 1 вчерашний и тд
    "cnt": 1,  # глубина опроса 1 за этот день 2 за этот и предыдущий и тп
    "overwrite": 0  # параметр дозаписи/перезаписи
}

json_string = json.dumps(json_create_cmd)
r.delete(f'channel.commands')

r.rpush(f'channel.commands', json_string) # добавляем его на редис
#---

channel_command = r.lpop(f'channel.commands')

address = json.loads(channel_command)["ph"]
I1 = json.loads(channel_command)["ago"]
I2 = json.loads(channel_command)["cnt"]
com = json.loads(channel_command)["cmd"]


r.delete(f'output')
answer_key = str(uuid.uuid4())
json_output = {"key": answer_key, "vmid": 4, "command": "day", "do": "send", "out":create_Packege(address,I1,I2,com),
               "protocol": "1", "waitingbytes": 28} # генерируем json с запросом и указываем ключ куда положить ответ

json_string = json.dumps(json_output)
r.rpush('output',json_string) #  добавляем его на редис

#--- создаем пример ответа  #C006770200008006020001A0F5940302100398CEA70204B0050CE0C0
json_answer = {"in": "C006770200008006020001A0F5940302100398CEA70204B0050CE0C0", "state": "0"}
json_string = json.dumps(json_answer)
r.rpush(answer_key,json_string)
#---

# c переодичностью в секунду проверяем:
json_answer = r.lpop(answer_key) # там лежит строка

json_data = check_ressive_and(json.loads(json_answer)["in"])
json_string = json.dumps(json_data)
r.rpush('data',json_string)






print(r.lpop('output'))
print(r.lpop('data'))



#98 CE A7 02
prim = [0] * 40
prim[0] = 0x10
prim[1] = 0
prim[2] = 0
prim[3] = 0


#print(DecodeDFF(prim,3))
#print(process_string('c006e703000000060200010001010200010103000101040001018e09c0'))




