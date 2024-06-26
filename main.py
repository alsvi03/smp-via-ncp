#!/usr/bin/env python3
import redis
import json
import uuid
import datetime
import time
import sys


def main():
    random_uuid = uuid.uuid4()  # рандомная генерация ключа
    command = sys.argv[1:]  # получение команды

    r = redis.Redis(host='redis', port=6379, db=0)  #тут поменять на нужный

    tBufUART: bytearray = [0] * 40
    int_buf: bytearray = [0] * 40
    e = 0  # 0- все ок, 1 - ошибка

    def process_string(input_string):  # приведение ответа к формату буфера
        buffer = []
        for i in range(0, len(input_string), 2):
            if i + 1 < len(input_string):
                two_chars = input_string[i:i + 2]
                num = two_chars
                buffer.append(num)

        return buffer

    def hex_to_int(buff):
        int_buf = [0] * len(buff)
        for i in range(len(buff)):
            int_buf[i] = int(buff[i], 16)
        return int_buf

    def DecodeDFF(recBuf, shiftInBits):  #перевод из dff в int
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
        crc = ncp_getCRC(buff, size - 3)

        if (crc >> 8) & 0xff == (buff[size - 3]) and (crc & 0xff) == (buff[size - 2]):
            return True
        else:
            return False

    # Если в данных надо передать байт 0xC0, то применяется механизм байnстаффинга – байт 0xС0
    # заменяется последовательностью 0xDB, 0xDC.
    # Если в данных надо передать байт 0xDB, то он заменяется последовательностью 0xDB, 0xDD.
    def byte_stuffing(buffer):
        stuffed_buffer = [buffer[0]]
        for i in range(1, len(buffer) - 1):
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

    def int_to_hex(buff, size, address):  # c00677020000000602000100000102000001030000010400000121aac0
        for i in range(size):
            hexval = hex(buff[i])
            hexstr = hexval[2:]
            if len(hexstr) == 1:
                tBufUART[i] = "0" + hexstr
            else:
                tBufUART[i] = hexstr

    def add_address():  # добавляем адрес в нужном формате
        hex_address = hex(address)[2:]
        if len(str(abs(address))) == 2:
            int_buf[2] = int(hex_address, 16)
        elif len(str(abs(address))) == 3:

            int_buf[2] = int(str(hex_address)[1:], 16)
            int_buf[3] = int("0" + str(hex_address)[:1], 16)

    def ncp_getCRC(buff, size):  # подсчет контрольной суммы
        NCP_CRC_POLYNOM = 0x8005
        crc = 0
        pcBlock = buff

        for i in range(1, size):
            crc ^= pcBlock[i] << 8
            for j in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ NCP_CRC_POLYNOM
                else:
                    crc = crc << 1
        return crc

    def ncp_addCRC(buff, size):  # добавление контрольной суммы в буфер
        crc = ncp_getCRC(buff, size)
        buff[size] = (crc >> 8) & 0xff
        buff[size + 1] = crc & 0xff
        return size + 2

    def DecToHex_CE318_NCP(buff, address):  # формирование адреса
        for i in range(4):
            buff[i + 2] = address[i]
        return

    def cut_Buf(buff):  # обрезает нули в конце буфера
        for i in range(len(buff) - 1, -1, -1):
            if buff[i] == 'c0':
                return buff[:i + 1]

        return buff

    def create_Packege(address, I1, I2, com, trf):

        int_buf[0] = 0xc0  # начальный байт
        int_buf[1] = 0x06
        add_address()  #[2-5] - адрес
        int_buf[6] = 0x00  # 0-отправка  80-получение
        int_buf[7] = 0x06  # 6-Данные для устройства 7- ошибка
        if com == 'day':  # формирование данных команды
            length = day_Data(int_buf, I1, I2,
                              trf)  # length - костыль чтобы потом знать в какие индексы записывать дальнейшие биты
        elif com == 'incday':
            length = day_Increment(int_buf, I1, I2, trf)
        elif com == 'month':
            length = month_Data(int_buf, I1, I2, trf)
        elif com == 'incmonth':
            length = month_Increment(int_buf, I1, I2, trf)
        elif com == 'allen':
            length = allen(int_buf, trf)
        elif com == 'min3':
            length = min3(int_buf)
        elif com == 'min30':
            length = min30(int_buf)
        elif com == 'instant':
            length = instant(int_buf)

        ncp_addCRC(int_buf, length)  # контрольная сумма пакета, 26-27 байты
        int_buf[length + 2] = 0xc0  # завершающий байт
        int_to_hex(int_buf, len(int_buf), address)  # перевод всего буфера в hex формат
        stuffed_buffer = byte_stuffing(cut_Buf(tBufUART))  # байт стаффинг

        out = ""
        for i in range(len(stuffed_buffer)):
            out += stuffed_buffer[i]

        return out

    def day_Data(buff, I1, I2, trf):
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

    def day_Increment(buff, I1, I2, trf):
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

    def month_Data(buff, I1, I2, trf):
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

    def month_Increment(buff, I1, I2, trf):
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

    def allen(buff, trf):  #
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
        buff[8] = 0x0a  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
        buff[9] = 0x00  # подкоманда
        buff[10] = 0x0e  # текущая мощность A+
        buff[11] = 0x0f  # текущая мощность A-
        buff[12] = 0x10  # текущая мощность R+
        buff[13] = 0x11  # текущая мощность R-
        return 14

    def min30(buff):

        # C0 06 77 02 00 00 80 06 01 00       12 00 13 14 15      BF 71 C0
        buff[8] = 0x0A  # номер команды (01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
        buff[9] = 0x00  # подкоманда
        buff[10] = 0x12  # A+
        buff[11] = 0x02
        buff[12] = 0x13  # A-
        buff[13] = 0x02
        buff[14] = 0x14  # R+
        buff[15] = 0x02
        buff[16] = 0x15  # R-
        buff[17] = 0x02

        return 18

    def instant(buff):
        # C0 06 77 02 00 00 00 06    0A 00 0E 1E 10 1E 16 1C 18 1C 19 1C 1A 1C    9E 89 C0
        buff[8] = 0x0a  # номер команды 0a - DATA_SINGLE_EX
        buff[9] = 0x00  # подкоманда
        buff[10] = 0x0e
        buff[11] = 0x1e
        buff[12] = 0x10
        buff[13] = 0x1e
        buff[14] = 0x16
        buff[15] = 0x1c
        buff[16] = 0x18
        buff[17] = 0x1c
        buff[18] = 0x19
        buff[19] = 0x1c
        buff[20] = 0x1a
        buff[21] = 0x1c
        return 22

    def check_ressive_and(answer,trf,g):
        global e
        buff = hex_to_int(byte_destuffing(process_string(answer)))  # обратный байт стаффинг и приведение к int
        if ncp_checkCRC(buff, len(buff)):  # проверка целостности пакета
            if buff[7] == 0x07:  # обработка ошибки
                if buff[8] == 1:
                    print("Ошибка. Используется если в кодах нет адекватной по смыслу ошибки.")
                elif buff[8] == 2:
                    print("Ошибка параметров")
                elif buff[8] == 3:
                    print("Неизвестный/пеподдерживаемый код")
                elif buff[8] == 4:
                    print("Ошибка записи")
                elif buff[8] == 5:
                    print("Недостаточно памяти")
                elif buff[8] == 6:
                    print("Неверный адрес")
                elif buff[8] == 7:
                    print("Некоректные данные в команде")
                elif buff[8] == 8:
                    print("Выполняется другая команда или устройство занято")
                elif buff[8] == 9:
                    print("Нет связи")
                e = 1
            elif buff[7] == 0x06:
                if buff[8] == 0x02:  #(01- DATA_SINGLE  02-GET_DATA_MULTIPLE)
                    if buff[10] == 0x01 or buff[10] == 0x05:  # начало суток
                        # запись данных в json
                        json_data = {"ep": check_Data(buff, 3)[0],
                                     "em": check_Data(buff, 3)[1],
                                     "rp": check_Data(buff, 3)[2],
                                     "rm": check_Data(buff, 3)[3],
                                     "tarif": trf,
                                     "date": (datetime.datetime.now() - datetime.timedelta(days=g)).strftime("%Y-%m-%d"),
                                     "time": "00:00:00",
                                     "poll_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                     "poll_time": datetime.datetime.now().strftime("%H:%M:%S"),
                                     }

                    elif buff[10] == 0x09 or buff[10] == 0x0d:  # Начало месяца
                        json_data = {"ep": check_Data(buff, 3)[0],
                                     "em": check_Data(buff, 3)[1],
                                     "rp": check_Data(buff, 3)[2],
                                     "rm": check_Data(buff, 3)[3],
                                     "tarif": trf,
                                     "date": (datetime.datetime.now() - timedelta(days=g*30)).replace(day=1).strftime("%Y-%m-%d"),
                                     "time": "00:00:00",
                                     "poll_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                     "poll_time": datetime.datetime.now().strftime("%H:%M:%S"), }

                elif buff[8] == 0x01:
                    json_data = {"ep": check_Data(buff, 0)[0],
                                 "em": check_Data(buff, 0)[1],
                                 "rp": check_Data(buff, 0)[2],
                                 "rm": check_Data(buff, 0)[3],
                                 "tarif": trf,
                                 "date": (datetime.datetime.now() - datetime.timedelta(days=g)).strftime("%Y-%m-%d"),
                                 "time": datetime.datetime.now().strftime("%H:%M:%S"),
                                 "poll_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                 "poll_time": datetime.datetime.now().strftime("%H:%M:%S"),
                                 }


                elif buff[10] == 0x0E:
                    json_data = {
                        "power_active": check_instant(buff)[0],
                        "power_active_phase_a": check_instant(buff)[1],
                        "power_active_phase_b": check_instant(buff)[2],
                        "power_active_phase_c": check_instant(buff)[3],
                        "power_reactive": check_instant(buff)[4],
                        "power_reactive_phase_a": check_instant(buff)[5],
                        "power_reactive_phase_b": check_instant(buff)[6],
                        "power_reactive_phase_c": check_instant(buff)[7],
                        "amperage_phase_a": check_instant(buff)[8],
                        "amperage_phase_b": check_instant(buff)[9],
                        "amperage_phase_c": check_instant(buff)[10],
                        "voltage": check_instant(buff)[11],
                        "voltage_phase_a": check_instant(buff)[12],
                        "voltage_phase_b": check_instant(buff)[13],
                        "voltage_phase_c": check_instant(buff)[14],
                        "power_coeff_plase_a": check_instant(buff)[15],
                        "power_coeff_plase_b": check_instant(buff)[16],
                        "power_coeff_plase_c": check_instant(buff)[17],
                        "frequency": check_instant(buff)[18],
                        "date": (datetime.datetime.now() - datetime.timedelta(days=g)).strftime("%Y-%m-%d"),
                        "time": datetime.datetime.now().strftime("%H:%M:%S"),
                        "poll_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                        "poll_time": datetime.datetime.now().strftime("%H:%M:%S"),
                    }
                elif buff[8] == 0x0A:
                    json_data = {"ep": check_Data(buff, 0)[0],
                                 "em": check_Data(buff, 0)[1],
                                 "rp": check_Data(buff, 0)[2],
                                 "rm": check_Data(buff, 0)[3],
                                 "tarif": trf,
                                 "date": (datetime.datetime.now() - datetime.timedelta(days=g)).strftime("%Y-%m-%d"),
                                 "time": datetime.datetime.now().strftime("%H:%M:%S"),
                                 "poll_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                 "poll_time": datetime.datetime.now().strftime("%H:%M:%S"),
                                 }

        else:
            print("Контрольная сумма пакета не совпадает")
            e = 1
        return json_data

    def check_Data(buff, shiftBits):
        ep = (DecodeDFF(buff[11:40], shiftBits)[0])/10000  # A+
        print("ep: ", ep)
        i = DecodeDFF(buff[11:40], shiftBits)[1] + 1
        em = (DecodeDFF(buff[11 + i:40], shiftBits)[0])/10000  # A-
        print("em: ", em)
        i = DecodeDFF(buff[11 + i:40], shiftBits)[1] + 1 + i
        rp = (DecodeDFF(buff[11 + i:40], shiftBits)[0])/10000  # R+
        print("rp: " ,rp)
        i = DecodeDFF(buff[11 + i:40], shiftBits)[1] + 1 + i
        rm = (DecodeDFF(buff[11 + i:40], shiftBits)[0])/10000  # R-
        print("rm: " ,rm)
        return ep, em, rp, rm

    def check_instant(buff):

        power_active = (DecodeDFF(buff[11:55], 3)[0]/10000) #0e
        i = DecodeDFF(buff[11:55], 3)[1]
        power_active_phase_a = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1]  + i
        power_active_phase_b = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] + i
        power_active_phase_c =( DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] + 1 + i
        power_reactive = (DecodeDFF(buff[11 + i:55], 3)[0] )/10000 #10
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        power_reactive_phase_a = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        power_reactive_phase_b = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        power_reactive_phase_c = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] + 1 + i
        amperage_phase_a =( DecodeDFF(buff[11 + i:55], 3)[0])/10000 #16
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        amperage_phase_b = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        amperage_phase_c = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] + 1 + i
        voltage = (DecodeDFF(buff[11 + i:55], 3)[0])/10000  #18
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        voltage_phase_a = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        voltage_phase_b = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        voltage_phase_c = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] + 1 + i
        power_coeff_plase_a = (DecodeDFF(buff[11 + i:55], 3)[0])/10000 #19
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        power_coeff_plase_b = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] +  i
        power_coeff_plase_c = (DecodeDFF(buff[11 + i:55], 3)[0])/10000
        i = DecodeDFF(buff[11 + i:55], 3)[1] + 1 + i
        frequency = (DecodeDFF(buff[11 + i:55], 3)[0])/10000 #1a
        i = DecodeDFF(buff[11 + i:55], 3)[1] + 1 + i

        return power_active,power_active_phase_a,power_active_phase_b,power_active_phase_c,power_reactive,power_reactive_phase_a,power_reactive_phase_b,power_reactive_phase_c,amperage_phase_a,amperage_phase_b,amperage_phase_c,voltage,voltage_phase_a,voltage_phase_b,voltage_phase_c,power_coeff_plase_a,power_coeff_plase_b,power_coeff_plase_c,frequency


    channel_command = r.lpop(f'{command[0]}.commands')
    print(f'{command[0]}.commands')
    print(channel_command)
    address = json.loads(channel_command)["ph"]
    I1 = json.loads(channel_command)["ago"]
    I2 = json.loads(channel_command)["cnt"]
    com = json.loads(channel_command)["cmd"]
    trf = int(json.loads(channel_command)["trf"])+1
    vm_id = json.loads(channel_command)["vm_id"]
    overwrite = json.loads(channel_command)["overwrite"]
    for g in range(I2):
        if com == 'instant':
            trf = 2

        for i in range(trf-1):
            answer_key = str(uuid.uuid4())  # создание ключа

            json_output = {"key": answer_key, "vmid": vm_id, "command": com, "do": "send",
                           "out": create_Packege(address, g, 0, com, pow(2,i)),
                           "protocol": "1",
                           "waitingbytes": 28}
            print(json_output)
            json_string = json.dumps(json_output)
            r.rpush(f'{command[0]}.output', json_string)  #  добавляем его на редис

            while True:

                json_answer = r.get(answer_key)
                if json_answer:
                    print(json_answer)
                    print(json.loads(json_answer)["in"])
                    json_data = check_ressive_and(json.loads(json_answer)["in"],i,g)  # разбираем ответ на данные
                    # данные для дозаписи
                    additional_data = {
                        "command": com,
                        "vm_id": vm_id,
                        "ago": I1,
                        "overwrite": overwrite,
                        "data": json_data,
                    }

                    json_string = json.dumps(additional_data)
                    r.rpush('dbwrite', json_string)  # кладем полученные данные в редис
                    print(f'JSON:{json_string}')
                    break  # Выход из цикла при получении ответа


    return e


main()
