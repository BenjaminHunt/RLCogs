import requests
from config import config

def main():
    api_key = "8d1250cac59b0fcc3859196eae8f840ee8b7179b"
    starting_cell = "A3"
    ending_cell = "C30"
    cell_range = "{}:{}".format(starting_cell, ending_cell)

    url = "https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{tab}!{cell_range}".format( # ?key={key}".format(
        sheet_id=config.RTL_id, 
        tab='List', 
        cell_range=cell_range # ,
        # key=api_key
    )

    data = requests.get(url).json()

    import pprint as pp 
    pp.pprint(data)

main()