import csv
import json

# Car bodies csv reference https://pastebin.com/i9Gf5t56

path_to_folder = "bcFunCommands/car_bodies"
car_lookup = {}

with open (f"{path_to_folder}/car_bodies.csv") as csv_file:
    reader = csv.reader(csv_file, delimiter=",")

    for row in reader:
        car_id = row[0]
        car_name = row[1]

        car_lookup[car_id] = car_name

print(f"OCTANE: {car_lookup.get('23')}")
assert(car_lookup.get('23') == "Octane")

with open(f"{path_to_folder}/car_bodies.json", "w") as cbjson:
    json.dump(car_lookup, cbjson)

print("Car Bodies JSON reference has been updated.")
