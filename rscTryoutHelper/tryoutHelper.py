
import requests
import json
import discord

import socket
from websocket import create_connection

class tryoutHelper(): #(commands.Cog):
    """Manages Members of a tryout server"""

    def __init__(self):
        # self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        # self.config.register_guild(**defaults)
        pass

    def get_sheets_range():
        pass 


    def sheet_helper():
        api_key = "8d1250cac59b0fcc3859196eae8f840ee8b7179b"
        starting_cell = "A3"
        ending_cell = "C30"
        cell_range = "{}:{}".format(starting_cell, ending_cell)

        url = "https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!{cell_range}?key={key}".format(
            sheet_id=sheet_id, 
            tab=tier, 
            cell_range=cell_range,
            key=api_key
        )

        data = requests.get(url).json()

        import pprint as pp 
        pp.pprint(data)
    
    def subscribe():
        pass 

    def main():
        PORT = 49122
        HOST = 'ws://localhost:{}'.format(PORT)

        ws = create_connection(HOST)
        
        while True:
            result = ws.recv()
            result = json.loads(result)
            print("Received '%s'" % result)

        ws.close()

# tryoutHelper.main()

print('a')
PORT = 49122
HOST = 'ws://localhost:{}'.format(PORT)

ws = create_connection(HOST)

while True:
    result = ws.recv()
    result = json.loads(result)
    print("Received '%s'" % result)

ws.close()
print('a')
