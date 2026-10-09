"""Generic demo data pack: a small invented manufacturer of training equipment.

Every code, name, price, customer and person here is made up. Run with:  manage.py seed
Copy this file to start a pack for your own business (see mes/datapacks/__init__.py).
"""
NAME = "generic"
CALIBRATE_TO_RRP = False
HOOKS = ("catalogue", "planning", "machines", "defects", "testreports")

TECHNICIANS = ["Alex", "Sam", "Jordan"]
STATIONS = ["Mechanical assembly", "PCB assembly", "Pneumatics", "Test bay", "Packing"]

FINISHED = [
    ("FG1001", "Conveyor Training Rig"),
    ("FG1002", "Pneumatics Trainer"),
    ("FG1003", "Sensor Workstation"),
    ("FG1004", "Motor Control Kit"),
    ("FG1005", "Robot Arm Cell"),
    ("FG1006", "Solar Energy Kit"),
    ("FG1007", "Bench Power Supply"),
    ("FG1008", "Programming Software Licence"),
]

ASSEMBLIES = [
    ("SA2001", "Conveyor frame assembly"),
    ("SA2002", "Drive motor unit"),
    ("SA2003", "Control panel assembly"),
    ("SA2004", "Valve block"),
    ("SA2005", "Sensor head"),
    ("SA2006", "Robot arm unit"),
    ("SA2007", "Base frame"),
    ("SA2008", "Controller board assembly"),
]

# (code, name, category, unit cost)
COMPONENTS = [
    ("ELE1001", "Stepper motor NEMA17", "ELE", "9.80"),
    ("ELE1002", "DC geared motor 24V", "ELE", "22.00"),
    ("ELE1003", "24V power supply 60W", "ELE", "14.50"),
    ("ELE1004", "Terminal block 2-way", "ELE", "0.25"),
    ("ELE1005", "Push-button switch", "ELE", "1.10"),
    ("ELE1006", "Limit switch", "ELE", "0.60"),
    ("ELE1007", "Proximity sensor", "ELE", "12.40"),
    ("ELE1008", "Emergency stop button", "ELE", "8.50"),
    ("ELE1009", "MCB 1 pole 6A", "ELE", "6.50"),
    ("ELE1010", "PLC controller", "ELE", "120.00"),
    ("ELE1011", "7 inch touch panel", "ELE", "180.00"),
    ("ELE1012", "Solar panel 5W", "ELE", "12.00"),
    ("CBL1001", "Lead 4mm red 500mm", "CBL", "0.90"),
    ("CBL1002", "Lead 4mm black 500mm", "CBL", "0.90"),
    ("CBL1003", "Cable 4-core (per metre)", "CBL", "0.45"),
    ("MEC1001", "Linear shaft 8mm x 300mm", "MEC", "3.20"),
    ("MEC1002", "Timing belt 6mm", "MEC", "2.40"),
    ("MEC1003", "Pulley 20 tooth", "MEC", "1.10"),
    ("MEC1004", "Ball bearing 608", "MEC", "0.35"),
    ("MEC1005", "Shaft support block", "MEC", "1.15"),
    ("FAS1001", "M3 x 8 socket screw", "FAS", "0.03"),
    ("FAS1002", "M4 x 10 socket screw", "FAS", "0.04"),
    ("FAS1003", "M3 nut", "FAS", "0.02"),
    ("FAS1004", "T-slot nut", "FAS", "0.12"),
    ("FAS1005", "M3 washer", "FAS", "0.01"),
    ("FAS1006", "Cable tie 100mm", "FAS", "0.02"),
    ("PCB1001", "Controller PCB blank", "PCB", "1.20"),
    ("PCB1002", "Driver PCB blank", "PCB", "0.95"),
    ("PCB1003", "Microcontroller", "PCB", "2.60"),
    ("PCB1004", "Resistor 10k 0603", "PCB", "0.02"),
    ("PCB1005", "Capacitor 10uF 0603", "PCB", "0.06"),
    ("PCB1006", "Voltage regulator 5V", "PCB", "0.34"),
    ("PNE1001", "Pneumatic cylinder 10 x 40", "PNE", "6.50"),
    ("PNE1002", "Solenoid valve 5/2", "PNE", "11.00"),
    ("PNE1003", "Tubing 4mm (per metre)", "PNE", "0.60"),
    ("PNE1004", "Push-in fitting 4mm", "PNE", "0.40"),
    ("PNE1005", "Vacuum cup 16mm", "PNE", "1.40"),
    ("MET1001", "Steel base plate", "MET", "4.40"),
    ("MET1002", "Aluminium extrusion 30 x 30 x 500", "MET", "6.50"),
    ("MET1003", "Mounting bracket", "MET", "0.28"),
    ("PLA1001", "Acrylic cover", "PLA", "0.80"),
    ("PLA1002", "Sensor holder (3D printed)", "PLA", "0.65"),
    ("RBT1001", "Robot arm mechanism", "RBT", "340.00"),
]

# parent code -> [(child code, quantity)]
BOM = {
    "SA2008": [("PCB1001", 1), ("PCB1003", 1), ("PCB1004", 12), ("PCB1005", 4), ("PCB1006", 1), ("ELE1004", 4)],
    "SA2007": [("MET1002", 4), ("MET1001", 1), ("FAS1002", 12), ("FAS1004", 8), ("MET1003", 4)],
    "SA2001": [("MET1001", 2), ("MET1003", 8), ("FAS1001", 16), ("FAS1004", 6), ("MEC1004", 4)],
    "SA2002": [("ELE1002", 1), ("MEC1002", 1), ("MEC1003", 2), ("MEC1004", 2), ("FAS1001", 8)],
    "SA2003": [("ELE1010", 1), ("ELE1011", 1), ("ELE1009", 1), ("ELE1008", 1), ("ELE1004", 12), ("SA2008", 1),
               ("FAS1006", 10)],
    "SA2004": [("PNE1002", 3), ("PNE1004", 8), ("PNE1003", 2), ("FAS1002", 4)],
    "SA2005": [("ELE1007", 1), ("PLA1002", 1), ("PLA1001", 1), ("FAS1001", 4)],
    "SA2006": [("RBT1001", 1), ("MET1001", 1), ("FAS1001", 12)],
    "FG1001": [("SA2001", 1), ("SA2002", 1), ("SA2003", 1), ("SA2005", 2), ("SA2007", 1), ("ELE1003", 1),
               ("CBL1001", 6), ("CBL1002", 6)],
    "FG1002": [("SA2004", 1), ("SA2007", 1), ("PNE1001", 2), ("PNE1005", 1), ("ELE1003", 1), ("ELE1005", 4),
               ("CBL1001", 4), ("CBL1002", 4)],
    "FG1003": [("SA2005", 3), ("SA2003", 1), ("SA2007", 1), ("ELE1003", 1), ("CBL1001", 6), ("CBL1002", 6)],
    "FG1004": [("SA2002", 1), ("SA2008", 1), ("ELE1003", 1), ("ELE1006", 2), ("CBL1001", 4), ("CBL1002", 4),
               ("MET1001", 1)],
    "FG1005": [("SA2006", 1), ("SA2003", 1), ("SA2007", 1), ("ELE1003", 1), ("MET1002", 6)],
    "FG1006": [("ELE1012", 2), ("CBL1001", 4), ("CBL1002", 4), ("ELE1003", 1), ("SA2008", 1)],
    "FG1007": [("ELE1003", 1), ("ELE1004", 2)],
}

# (name, kind, status, location, notes); status: available | in_use | maintenance | down
MACHINES = [
    ("Laser cutter", "Fibre laser cutting cell", "available", "Machine shop", "Sheet metal cutting"),
    ("Press brake", "CNC hydraulic press brake", "in_use", "Machine shop", "Bending"),
    ("CNC mill", "Vertical machining centre", "in_use", "Machine shop", "Running; coolant topped up weekly"),
    ("CNC lathe", "Turning centre", "available", "Machine shop", ""),
    ("3D printer", "Additive", "in_use", "Prototype room", "4 printers"),
    ("Soldering station", "Electronics", "available", "Electronics bay", ""),
    ("Reflow oven", "Electronics", "down", "Electronics bay", "Heater element failed; awaiting part"),
    ("Wire cut and crimp", "Electronics", "available", "Electronics bay", ""),
    ("Test rig", "Test", "available", "Test bay", "Safety and functional testing"),
    ("Pneumatic test bench", "Test", "maintenance", "Test bay", "Annual calibration in progress"),
]

# product code -> [(step name, machine name or None, minutes)]
ROUTINGS = {
    "SA2008": [("Solder components", "Soldering station", 25), ("Reflow and inspect", "Reflow oven", 10),
               ("Functional test", "Test rig", 8)],
    "SA2007": [("Cut plates", "Laser cutter", 10), ("Machine mounts", "CNC mill", 18), ("Assemble frame", None, 20)],
    "SA2001": [("Cut sheet metal", "Laser cutter", 8), ("Bend", "Press brake", 6), ("Assemble frame", None, 25)],
    "SA2002": [("Turn shafts", "CNC lathe", 12), ("Assemble motor unit", None, 18)],
    "SA2003": [("Mount components", None, 40), ("Wiring", "Wire cut and crimp", 55), ("Test", "Test rig", 20)],
    "SA2004": [("Assemble valve block", None, 12), ("Pneumatic test", "Pneumatic test bench", 6)],
    "SA2005": [("3D print holders", "3D printer", 15), ("Assemble sensor head", None, 20), ("Test", "Test rig", 6)],
    "SA2006": [("Assemble arm", None, 50), ("Calibrate", "Test rig", 25)],
    "FG1001": [("Final assembly", None, 70), ("Functional test", "Test rig", 40), ("Pack", None, 12)],
    "FG1002": [("Final assembly", None, 60), ("Pneumatic test", "Pneumatic test bench", 15),
               ("Functional test", "Test rig", 20), ("Pack", None, 12)],
    "FG1003": [("Final assembly", None, 45), ("Functional test", "Test rig", 25), ("Pack", None, 10)],
    "FG1004": [("Final assembly", None, 40), ("Functional test", "Test rig", 25), ("Pack", None, 10)],
    "FG1005": [("Final assembly", None, 60), ("Functional test", "Test rig", 40), ("Pack", None, 15)],
    "FG1006": [("Assemble", None, 25), ("Functional test", "Test rig", 15), ("Pack", None, 8)],
    "FG1007": [("Assemble", None, 6), ("Functional test", "Test rig", 4)],
}

RRP = {"FG1001": 1950, "FG1002": 550, "FG1003": 1750, "FG1004": 380, "FG1005": 2700, "FG1006": 280,
       "FG1007": 55, "FG1008": 450}

# number, product, qty, station, due in N days, status, technician, est minutes (whole order)
LIVE_ORDERS = [
    ("1101", "FG1001", 5, "Test bay", 3, "entered", None, 150),
    ("1102", "SA2001", 10, "Mechanical assembly", 2, "in_progress", "Alex", 240),
    ("1103", "SA2007", 5, "Mechanical assembly", 4, "qa", "Sam", 75),
    ("1104", "SA2002", 5, "Mechanical assembly", 5, "allocated", None, 100),
    ("1105", "SA2005", 10, "PCB assembly", 6, "issued", "Jordan", 120),
    ("1106", "SA2004", 10, "Pneumatics", 7, "entered", None, 90),
    ("1107", "SA2008", 20, "PCB assembly", 4, "issued", "Jordan", 200),
    ("1108", "FG1006", 3, "Packing", 10, "entered", None, 45),
    ("1109", "FG1005", 2, "Test bay", 12, "allocated", "Sam", 180),
    ("1110", "FG1002", 4, "Pneumatics", 14, "entered", None, 160),
]
HISTORY_PRODUCTS = ["SA2001", "SA2007", "SA2002", "SA2005", "SA2004", "SA2008"]
HISTORY_STATIONS = ["Mechanical assembly", "PCB assembly"]
HISTORY_START_NUMBER = 1099

# number, days ago, customer, reference, [(product, qty)]
CUSTOMER_ORDERS = [
    ("5001", 20, "Northfield Technical College", "Phone order", [("FG1008", 1), ("FG1007", 1), ("FG1004", 1)]),
    ("5002", 14, "Brightwater Academy", "PO-4471", [("FG1001", 3), ("FG1007", 3)]),
    ("5003", 9, "Kestrel Engineering Training", "Email order", [("FG1005", 2), ("FG1004", 2)]),
    ("5004", 5, "Harlow Sixth Form", "PO-1182", [("FG1006", 4)]),
    ("5005", 2, "Ironbridge Skills Centre", "Web order", [("FG1002", 2), ("FG1003", 6), ("FG1007", 2)]),
    ("5006", 1, "Pennine Robotics Club", "Phone order", [("FG1004", 5), ("FG1007", 5)]),
]

CUSTOMERS = [
    "Brookfield Technical College", "Ashworth Academy of Engineering", "Kingsmere Training Centre",
    "Redcliffe Further Education College", "Harlow Vale Skills Academy", "Westmoor University Technical Faculty",
    "Pennine Apprenticeship Centre", "Lakeside Engineering College", "Ironbridge Training Academy",
    "Stonegate Polytechnic", "Marlow Heath Sixth Form College", "Cardigan Bay Skills Centre",
    "Thornbury Vocational Institute", "Eastgate Learning Centre", "Highmoor Technology Academy",
]

# Weighted so a few products are clear best sellers.
BEST_SELLERS = {"FG1001": 10, "FG1002": 8, "FG1004": 6, "FG1006": 6, "FG1003": 4, "FG1005": 3}

# number, days since ordered, customer, ship in N days, [(product, qty, status, due in N days, technician) or
# (product, qty) for a line with no works order raised yet]
PLANNING_ORDERS = [
    ("6001", 12, "Millbrook Engineering Academy", -4,
     [("FG1001", 2, "in_progress", -6, "Alex"), ("FG1007", 2, "in_progress", -3, "Sam")]),
    ("6002", 10, "Cedarwood Sixth Form College", 3,
     [("FG1006", 3, "in_progress", 1, "Jordan"), ("FG1004", 10, "issued", 2, "Sam")]),
    ("6003", 8, "Fenwick Technical Institute", 9,
     [("FG1002", 5, "allocated", 6, "Alex"), ("FG1003", 4)]),
    ("6004", 6, "Oakridge Skills Academy", 14,
     [("FG1005", 3, "allocated", 10, "Jordan"), ("FG1003", 6, "entered", 11, None)]),
    ("6005", 5, "Silverbeck Training Centre", 20,
     [("FG1001", 2, "entered", 16, None), ("FG1004", 2, "entered", 17, None)]),
    ("6006", 3, "Wexcombe College of Technology", 27,
     [("FG1001", 6, "entered", 22, None), ("FG1006", 4, "entered", 24, None)]),
    ("6007", 2, "Dunmere Maker Space", 36,
     [("FG1002", 8, "entered", 30, None), ("FG1005", 8, "entered", 32, None)]),
    ("6008", 1, "Alderley Apprentice Hub", 50,
     [("FG1006", 5, "entered", 42, None), ("FG1004", 3)]),
]

# Stock builds not tied to a customer order: product, qty, status, due in N days, technician.
STOCK_BUILDS = [
    ("SA2001", 12, "in_progress", 3, "Alex"), ("SA2008", 30, "issued", 5, "Sam"),
    ("SA2007", 8, "allocated", 8, "Jordan"), ("SA2005", 16, "entered", 12, None),
    ("SA2002", 8, "entered", 15, None), ("SA2004", 4, "allocated", 9, "Alex"),
    ("SA2006", 3, "entered", 19, None), ("SA2003", 12, "issued", -3, "Jordan"),
    ("SA2001", 6, "in_progress", -1, "Sam"),
]

MACHINE_NOTES = {
    "Soldering station": "Lead-free; tip change every 2 weeks",
    "Wire cut and crimp": "Handles 0.5 to 2.5 mm2 cable",
    "Pneumatic test bench": "Rated to 8 bar; calibration certificate on file",
    "CNC lathe": "Used for spacers and shafts; service due next month",
}
