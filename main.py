import redis #  redis-server
import json



# мгновенное значение, коррекция и установка времени, 30-минутные мощности, 3-х минутки?


r = redis.Redis(host='localhost', port=6379, db=0)

tBufUART: bytearray = [0] * 40
int_buf: bytearray = [0] * 40


def check_ressive_and(buff):
    #buff[6] == 0x80  # 0-отправка  80-получение
    crc = (buff[len(buff)-2] << 8) | buff[len(buff)-1]
    if ncp_getCRC(buff,len(buff)) == crc: # проверка целостности пакета
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
            elif buff[10] == 0x05: # 5 команда (запрос Накопление энергии A+ за сутки)
                check_Day_Increment(buff)
            elif buff[10] == 0x09: # 9 команда (запрос Накопление энергии A+ на начало расчетного периода(месяца))
                check_Month_Data(buff)
            elif buff[10] == 0x0d:  # 13 команда (запрос Накопление энергии A+ за расчетный период (месяц))
                check_Month_Increment(buff)

    else:
        print("Контрольная сумма пакета не совпадает")




def check_Day_Data(buff):
    # buff [14-15, 20-21, 26-27, 32-33] (вроде как) в этих битах лежат данные А+ А- R+ R-
    # эти данные отдаем назад
    i=0 #чтобы не выдавало ошибку пока функция пустая

def check_Day_Increment(buff):
    i=0

def check_Month_Data(buff):
    i=0

def check_Month_Increment(buff):
    i=0




# Если в данных надо передать байт 0xC0, то применяется механизм байnстаффинга – байт 0xС0
# заменяется последовательностью 0xDB, 0xDC.
# Если в данных надо передать байт 0xDB, то он заменяется последовательностью 0xDB, 0xDD.
def byte_stuffing(buffer):
    stuffed_buffer = [buffer[0]]
    for i in range(1, len(buffer)-1):
        if buffer[i] == '0xc0':
            stuffed_buffer.extend(['0xdb', '0xdc'])
        elif buffer[i] == '0xdb':
            stuffed_buffer.extend(['0xdb', '0xdd'])
        else:
            stuffed_buffer.append(buffer[i])
    stuffed_buffer.append(buffer[-1])
    return stuffed_buffer


def int_to_hex(buff,size):

    for i in range(size):
        tBufUART[i] = hex(buff[i])


def ncp_getCRC(buff, size):
    NCP_CRC_POLYNOM = 0x8005
    crc = 0
    pcBlock = buff


    for i in range(size):
        crc ^= pcBlock[i] << 8
        for j in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ NCP_CRC_POLYNOM
            else:
                crc = crc << 1
    return crc

def ncp_addCRC(buff, size):
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
        if buff[i] == '0xc0':
            return buff[:i + 1]

    return buff

def create_Packege(address,I1,I2,com):
    int_buf[0] = 0xc0
    int_buf[1] = 0x06
    DecToHex_CE318_NCP(int_buf, address)  # адресс, 2-5 байты
    int_buf[6] = 0x00  # 0-отправка  1-получение
    int_buf[7] = 0x06  # 6-Данные для устройства 7- ошибка
    int_buf[8] = 0x02  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
    int_buf[9] = 0x00  # подкоманда

    if com == 1: # формирование данных команды
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
    int_to_hex(int_buf, len(int_buf)) # перевод всего буфера в hex формат

    stuffed_buffer = byte_stuffing(cut_Buf(tBufUART))

    out =""
    for i in range (len(cut_Buf(stuffed_buffer))):
        out += stuffed_buffer[i]

    #return cut_Buf(tBufUART)
    return out

def day_Data(buff,I1,I2):
    buff[10] = 0x01  # 1 команда (запрос Накопление энергии A+ на начало суток)
    buff[11] = 0x00  # Маска, общая энергия
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



if __name__ == "__main__":



    r.delete('address')

    r.lpush('address','1')
    r.lpush('address','12')
    r.lpush('address','7')
    r.lpush('address','15')

    #print(r.lrange('address',0,-1))

    address = [0] * 4 # адрес (получаем на входе)
    address[0]=1
    address[1]=12
    address[2]=7
    address[3]=15



    I1 = 0 # диапазон данных (получаем на входе)
    I2 = 15

    com = 1 # номер команды (получаем на входе)






#-- создаем пример запроса
json_create_cmd = {
    "channel": 'ktp6',  # название канала
    "cmd": 'day',  # название типа опроса day - показания на начало суток
    "run": 'ce318',  # название вызываемого протокола
    "vm_id": 4,  # id прибора учёта
    "ph": 31,  # адрес под которым счетчик забит в успд
    "trf": '4',  # количество тарифов у счётчика
    "ki": 2,  # коэф тока
    "ku": 3,  # коэф трансформации
    "ago": 0,  # начало опроса 0 - текущий день 1 вчерашний и тд
    "cnt": 1,  # глубина опроса 1 за этот день 2 за этот и предыдущий и тп
    "overwrite": 0  # параметр дозаписи/перезаписи
}

json_string = json.dumps(json_create_cmd)

r.rpush(f'channel.commands', json_string) # добавляем его на редис
#---

json_output = {"key": "{answer}", "vmid": 4, "command": "day", "do": "send", "out":create_Packege(address,I1,I2,1)
,"protocol": "1", "waitingbytes": 22} # генерируем json с запросом и указываем ключ куда положить ответ

json_string = json.dumps(json_output)
r.rpush('output',json_string) #  добавляем его на редис

#--- создаем пример ответа
json_answer = {"in": "3E032A00A1413000B82F0100113442005FB300005E5C", "state": "0"}
json_string = json.dumps(json_answer)
r.rpush('answer',json_string)
#---

# c переодичностью в секунду проверяем:
json_answer = r.lpop('answer') # там лежит строка




#print(json_answer)
print(r.lpop('output'))