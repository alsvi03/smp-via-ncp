import redis
import json
import uuid
import datetime
import time

#redis-cli
#keys *
#lrange channel.commands 0 -1

random_uuid = uuid.uuid4() # рандомная генерация ключа

#30-минутные мощности, по фазам('instant')
# тариф в выводе


# коррекция и установка времени
# dff зашифровка



r = redis.Redis(host='localhost', port=6379, db=0)
r.delete(f'output')
r.delete(f'data')
r.delete(f'channel.commands')



tBufUART: bytearray = [0] * 40
int_buf: bytearray = [0] * 40

def process_string(input_string):  # приведение ответа к формату буфера
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

def create_Packege(address,I1,I2,com,trf):

    int_buf[0] = 0xc0 # начальный байт
    int_buf[1] = 0x06
    add_address()     #[2-5] - адрес
    int_buf[6] = 0x00  # 0-отправка  80-получение
    int_buf[7] = 0x06  # 6-Данные для устройства 7- ошибка
    if com == 'day': # формирование данных команды
        length = day_Data(int_buf,I1,I2,trf) # length - костыль чтобы потом знать в какие индексы записывать дальнейшие биты
    elif com == 'incday':
        length = day_Increment(int_buf,I1,I2,trf)
    elif com == 'month':
        length = month_Data(int_buf,I1,I2,trf)
    elif com == 'incmonth':
        length = month_Increment(int_buf,I1,I2,trf)
    elif com == 'allen':
        length = allen(int_buf,trf)
    elif com == 'min3':
        length = min3(int_buf)
    elif com == 'min30':
        length = min30(int_buf)
    elif com == 'instant':
        length = instant(int_buf)

    ncp_addCRC(int_buf, length)  # контрольная сумма пакета, 26-27 байты
    int_buf[length+2] = 0xc0 # завершающий байт
    int_to_hex(int_buf, len(int_buf),address) # перевод всего буфера в hex формат
    stuffed_buffer = byte_stuffing(cut_Buf(tBufUART)) # байт стаффинг

    out =""
    for i in range (len(stuffed_buffer)):
        out += stuffed_buffer[i]


    return out





def day_Data(buff,I1,I2,trf):
    buff[8] = 0x02  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x01  # 1 команда (запрос Накопление энергии A+ на начало суток)
    buff[11] = trf  # Маска, общая энергия (тариф?) 0 - общая 1 - суммарная 2 - первый тариф 3 - второй и тд
    buff[12] = I1  # номер более поздних суток
    buff[13] = I2  # номер более ранних суток
    buff[14] = 0x02  # 2 команда (запрос Накопление энергии A- на начало суток)
    buff[15] = trf  # Маска, общая энергия
    buff[16] = I1  # номер более поздних суток
    buff[17] = I2  # номер более ранних суток
    buff[18] = 0x03  # 3 команда (запрос Накопление энергии R+ на начало суток)
    buff[19] = trf  # Маска, общая энергия
    buff[20] = I1  # номер более поздних суток
    buff[21] = I2  # номер более ранних суток
    buff[22] = 0x04  # 4 команда (запрос Накопление энергии R- на начало суток)
    buff[23] = trf  # Маска, общая энергия
    buff[24] = I1  # номер более поздних суток
    buff[25] = I2  # номер более ранних суток
    return 26

def day_Increment(buff,I1,I2,trf):
    buff[8] = 0x02  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x05  # 5 команда (запрос Накопление энергии A+ за сутки)
    buff[11] = trf  # Маска, общая энергия
    buff[12] = I1  # номер более поздних суток
    buff[13] = I2  # номер более ранних суток
    buff[14] = 0x06  # 6 команда (запрос Накопление энергии A- за сутки)
    buff[15] = trf  # Маска, общая энергия
    buff[16] = I1  # номер более поздних суток
    buff[17] = I2  # номер более ранних суток
    buff[18] = 0x07  # 7 команда (запрос Накопление энергии R+ за сутки)
    buff[19] = trf  # Маска, общая энергия
    buff[20] = I1  # номер более поздних суток
    buff[21] = I2  # номер более ранних суток
    buff[22] = 0x08  # 8 команда (запрос Накопление энергии R- за сутки)
    buff[23] = trf  # Маска, общая энергия
    buff[24] = I1  # номер более поздних суток
    buff[25] = I2  # номер более ранних суток
    return 26

    
def month_Data(buff,I1,I2,trf):
    buff[8] = 0x02  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x09  # 9 команда (запрос Накопление энергии A+ на начало расчетного периода(месяца))
    buff[11] = trf  # Маска, общая энергия
    buff[12] = I1  # номер более позднего месяца
    buff[13] = I2  # номер более раннего месяца
    buff[14] = 0x0A  # 10 команда (запрос Накопление энергии A- на начало расчетного периода(месяца))
    buff[15] = trf  # Маска, общая энергия
    buff[16] = I1  # номер более позднего месяца
    buff[17] = I2  # номер более раннего месяца
    buff[18] = 0x0B  # 11 команда (запрос Накопление энергии R+ на начало расчетного периода(месяца))
    buff[19] = trf  # Маска, общая энергия
    buff[20] = I1  # номер более позднего месяца
    buff[21] = I2  # номер более раннего месяца
    buff[22] = 0x0C  # 12 команда (запрос Накопление энергии R- на начало расчетного периода(месяца))
    buff[23] = trf  # Маска, общая энергия
    buff[24] = I1  # номер более позднего месяца
    buff[25] = I2  # номер более раннего месяца
    return 26
    
def month_Increment(buff,I1,I2,trf):
    buff[8] = 0x02  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x0d  # 13 команда (запрос Накопление энергии A+ за расчетный период (месяц))
    buff[11] = trf  # Маска, общая энергия
    buff[12] = I1  # номер более позднего месяца
    buff[13] = I2  # номер более раннего месяца
    buff[14] = 0x0e  # 14 команда (запрос Накопление энергии A- за расчетный период (месяц))
    buff[15] = trf  # Маска, общая энергия
    buff[16] = I1  # номер более позднего месяца
    buff[17] = I2  # номер более раннего месяца
    buff[18] = 0x0f  # 15 команда (запрос Накопление энергии R+ за расчетный период (месяц))
    buff[19] = trf  # Маска, общая энергия
    buff[20] = I1  # номер более позднего месяца
    buff[21] = I2  # номер более раннего месяца
    buff[22] = 0x10  # 16 команда (запрос Накопление энергии R- за расчетный период (месяц))
    buff[23] = trf  # Маска, общая энергия
    buff[24] = I1  # номер более позднего месяца
    buff[25] = I2  # номер более раннего месяца
    return 26



def allen(buff,trf): #
    buff[8] = 0x01  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x01  # текущее накопление энергии A+
    buff[11] = trf  # Маска, общая энергия
    buff[12] = 0x02  # текущее накопление энергии A-
    buff[13] = trf  # Маска, общая энергия
    buff[14] = 0x03  # текущее накопление энергии R+
    buff[15] = trf  # Маска, общая энергия
    buff[16] = 0x04  # текущее накопление энергии R-
    buff[17] = trf  # Маска, общая энергия

    return 18




def min3(buff):
    #C0 06 77 02 00 00 80 06 01 00   0E 21 00 03 00 03 00 03   10 05 00 03 00 03 00 03    70 D7 C0
    #C0 06 77 02 00 00 80 06 01 00   0E 16   00 03   10 06   00 03                            B2 AC C0
    buff[8] = 0x01  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x0e  # текущая мощность A+
    buff[11] = 0x0f  # текущая мощность A-
    buff[12] = 0x10  # текущая мощность R+
    buff[13] = 0x11  # текущая мощность R-
    return 14

def min30(buff):
    buff[8] = 0x0a  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x12  #  A+
    buff[11] = 0x13  #  A-
    buff[12] = 0x14  #  R+
    buff[13] = 0x15  #  R-

    return 14

def instant (buff): #
    buff[8] = 0x0a  # номер команды 0a - DATA_SINGLE_EX
    buff[9] = 0x00  # подкоманда
    buff[10] = 0x0d
    buff[11] = 0x1e
    buff[12] = 0x0e
    buff[13] = 0x1e
    buff[14] = 0x10
    buff[15] = 0x1e
    buff[16] = 0x16
    buff[17] = 0x1c
    buff[18] = 0x18
    buff[19] = 0x1c
    buff[20] = 0x19
    buff[21] = 0x1c
    buff[22] = 0x1a
    buff[23] = 0x1c
    buff[24] = 0x52
    buff[25] = 0x1c
    buff[26] = 0x53
    buff[27] = 0x1c
    buff[28] = 0x54
    buff[29] = 0x1c
    return 30




def check_ressive_and(answer):
    buff = hex_to_int(byte_destuffing(process_string(answer))) # обратный байт стаффинг и приведение к int
    if ncp_checkCRC(buff,len(buff)): # проверка целостности пакета
        if buff[7] == 0x07: # обработка ошибки
            if buff[8]== 1:
                json_data = {"error":"Error. Used if the codes do not contain an error that is adequate in meaning."}
            elif buff[8] == 2:
                json_data = {"error":"Parameter error"}
            elif buff[8] == 3:
                json_data = {"error":"Unknown/unsupported code"}
            elif buff[8] == 4:
                json_data = {"error": "Write error"}
            elif buff[8] == 5:
                json_data = {"error": "Not enough memory"}
            elif buff[8] == 6:
                json_data = {"error": "Wrong address"}
            elif buff[8] == 7:
                json_data = {"error": "Incorrect data in the command"}
            elif buff[8] == 8:
                json_data = {"error": "Another command is in progress or the device is busy"}
            elif buff[8] == 9:
                json_data = {"error": "No connection"}
        elif buff[7] == 0x06:
            if buff[8] == 0x02: #(01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
                # запись данных в json
                json_data = {"ep": check_Data(buff,3)[0],
                             "em": check_Data(buff,3)[1],
                             "rp": check_Data(buff,3)[2],
                             "rm": check_Data(buff,3)[3],
                             "tarif": 0,
                             "date": datetime.datetime.now().strftime("%d-%m-%Y"),
                             "time":  datetime.datetime.now().strftime("%H:%M:%S"),
                             "poll_date": datetime.datetime.now().strftime("%d-%m-%Y"),
                             "poll_time": datetime.datetime.now().strftime("%H:%M:%S")}
            elif buff[8] == 0x01:
                json_data = {"ep": check_Data(buff,0)[0],
                             "em": check_Data(buff,0)[1],
                             "rp": check_Data(buff,0)[2],
                             "rm": check_Data(buff,0)[3],
                             "tarif": 0,
                             "date": datetime.datetime.now().strftime("%d-%m-%Y"),
                             "time": datetime.datetime.now().strftime("%H:%M:%S"),
                             "poll_date": datetime.datetime.now().strftime("%d-%m-%Y"),
                             "poll_time": datetime.datetime.now().strftime("%H:%M:%S")}






    else:
        json_data = {"error": 'Packet checksum does not match'}

    return json_data




def check_Data(buff,shiftBits):
    ep = DecodeDFF(buff[11:40],shiftBits)[0] # A+
    i = DecodeDFF(buff[11:40], shiftBits)[1] + 1
    em = DecodeDFF(buff[11+i:40],shiftBits)[0] # A-
    i = DecodeDFF(buff[11+i:40], shiftBits)[1] + 1+i
    rp = DecodeDFF(buff[11 + i:40], shiftBits)[0] # R+
    i = DecodeDFF(buff[11+i:40], shiftBits)[1] + 1+i
    rm = DecodeDFF(buff[11 + i:40], shiftBits)[0] # R-

    return ep,em,rp,rm










#-- создаем пример запроса
json_create_cmd = {
    "channel": 'ktp6',  # название канала
    "cmd": 'min3',  # название типа опроса day - показания на начало суток
    "run": 'ce318',  # название вызываемого протокола
    "vm_id": 4,  # id прибора учёта
    "ph": 631,  # адрес под которым счетчик забит в успд
    "trf": '3',  # количество тарифов у счётчика
    "ki": 2,  # коэф тока
    "ku": 3,  # коэф трансформации
    "ago": 0,  # начало опроса 0 - текущий день 1 вчерашний и тд
    "cnt": 0,  # глубина опроса 1 за этот день 2 за этот и предыдущий и тп
    "overwrite": 0  # параметр дозаписи/перезаписи
}

json_string = json.dumps(json_create_cmd)

r.rpush(f'channel.commands', json_string) # добавляем его на редис
#---


# разбор полученного jsonа на данные
channel_command = r.lpop(f'channel.commands')

address = json.loads(channel_command)["ph"]
I1 = json.loads(channel_command)["ago"]
I2 = json.loads(channel_command)["cnt"]
com = json.loads(channel_command)["cmd"]
trf = json.loads(channel_command)["trf"]




for i in range(int(trf)):

    answer_key = str(uuid.uuid4()) # создание ключа
    json_output = {"key": answer_key, "vmid": 4, "command": "day", "do": "send", "out":create_Packege(address,I1,I2,com,i),
                   "protocol": "1", "waitingbytes": 28} # генерируем json с запросом и указываем ключ куда положить ответ

    json_string = json.dumps(json_output)
    r.rpush('output',json_string) #  добавляем его на редис

#--- создаем пример ответа
#C006770200008006020001D0B98D0102100388CB7404B005CD91C0  накопление энергии на начало суток по первому тарифу
#C0067702000080060100019AD711020203B1C90E04560CA0C0  текущее накопление энергии
json_answer = {"in": "C0067702000080060100019AD711020203B1C90E04560CA0C0", "state": "0"}
json_string = json.dumps(json_answer)
r.rpush(answer_key,json_string)
#---

# c переодичностью в секунду проверяем:

while True:
    json_answer = r.lpop(answer_key)

    if json_answer:
        json_data = check_ressive_and(json.loads(json_answer)["in"])  # разбираем ответ на данные
        json_string = json.dumps(json_data)
        r.rpush('data', json_string)  # кладем полученные данные в редис
        break  # Выход из цикла при получении ответа
    time.sleep(1)  # Подождать 1 секунду перед следующей итерацией





#
# prim = [0] *  10
# prim[0] =0xB1
# prim[1] =0xC9
# prim[2] =0x0E
#
#

# print(DecodeDFF(prim,0))

print(r.lpop('output'))
print(r.lpop('output'))
print(r.lpop('output'))
print(r.lpop('output'))

print(r.lpop('data'))
