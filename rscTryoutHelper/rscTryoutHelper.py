from .config import config
import requests
import json
import discord

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

import socket


defaults =   {
    "RTL": config.RTL_id,
    "MMS": config.MMS_id,
    "AuthKey": config.auth_key
}

class rscTryoutHelper(commands.Cog):
    """Manages Members of a tryout server"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
    

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
    
    def main():
        host = 'ws://localhost'
        port = 49122

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            conn, addr = s.accept()
            with conn:
                print('Connected by', addr)
                while True:
                    data = conn.recv(1024)
                    print("> {}".format(data))
                    if not data:
                        break
        

rscTryoutHelper.main()