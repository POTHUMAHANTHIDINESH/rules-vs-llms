"""Schema + reference knowledge for NYC 311 (CSV-export column names)."""
COLS = ["Unique Key", "Created Date", "Closed Date", "Agency", "Complaint Type", "Descriptor", "Location Type",
        "Incident Zip", "City", "Borough", "Latitude", "Longitude", "Status", "Resolution Description",
        "Open Data Channel Type"]
NUMERIC = ["Unique Key", "Latitude", "Longitude"]
DATE_COLS = ["Created Date", "Closed Date"]
DATE_FMT = "%m/%d/%Y %I:%M:%S %p"
DATE_RE = r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} (AM|PM)$"
TEXT_COLS = ["Descriptor", "Resolution Description"]
NYC_LAT, NYC_LON = (40.40, 41.00), (-74.30, -73.60)

# complaint type -> (agency, [descriptors])
COMPLAINTS = {
    "Noise - Residential": ("NYPD", ["Loud Music/Party", "Banging/Pounding", "Loud Talking", "Loud Television"]),
    "Noise - Street/Sidewalk": ("NYPD", ["Loud Music/Party", "Loud Talking", "Car/Truck Music"]),
    "Illegal Parking": ("NYPD", ["Blocked Hydrant", "Double Parked Blocking Traffic", "Blocked Sidewalk", "Posted Parking Sign Violation"]),
    "Blocked Driveway": ("NYPD", ["Partial Access", "No Access"]),
    "HEAT/HOT WATER": ("HPD", ["ENTIRE BUILDING", "APARTMENT ONLY"]),
    "PLUMBING": ("HPD", ["BATHTUB/SHOWER", "TOILET", "KITCHEN/BATHROOM SINK"]),
    "UNSANITARY CONDITION": ("HPD", ["PESTS", "MOLD", "GARBAGE/RECYCLING STORAGE"]),
    "Street Condition": ("DOT", ["Pothole", "Pavement Defect", "Manhole Cover"]),
    "Street Light Condition": ("DOT", ["Street Light Out", "Lamppost Damaged"]),
    "Missed Collection": ("DSNY", ["1 Missed Trash Collection", "2 Missed Recycling Collection"]),
    "Dirty Condition": ("DSNY", ["Trash", "Litter Basket / Request"]),
    "Water System": ("DEP", ["Leak", "No Water", "Low Pressure"]),
    "Sewer": ("DEP", ["Catch Basin Clogged/Flooding", "Sewer Backup"]),
    "Rodent": ("DOHMH", ["Rat Sighting", "Mouse Sighting", "Condition Attracting Rodents"]),
}
AGENCY_NAME = {"NYPD": "New York City Police Department", "HPD": "Department of Housing Preservation and Development",
               "DOT": "Department of Transportation", "DSNY": "Department of Sanitation",
               "DEP": "Department of Environmental Protection", "DOHMH": "Department of Health and Mental Hygiene"}
AGENCY_SHORT = {"NYPD": "The Police Department", "HPD": "The Department of Housing Preservation and Development",
                "DOT": "The Department of Transportation", "DSNY": "The Department of Sanitation",
                "DEP": "The Department of Environmental Protection", "DOHMH": "The Department of Health and Mental Hygiene"}
CLOSED_TPL = ["{a} responded to the complaint and took action to fix the condition.",
              "{a} investigated and resolved the complaint.",
              "{a} inspected the location and determined that no violation was found. This request is closed.",
              "{a} completed the requested work and closed this request."]
OPEN_TPL = ["Your request has been received by {a} and is awaiting assignment.",
            "{a} is reviewing your request and has not yet completed it; the status will be updated.",
            "Your complaint was assigned to an inspector at {a} and is still pending."]
BOROUGH_ZIPS = {
    "MANHATTAN": [f"100{n:02d}" for n in list(range(1, 8)) + list(range(9, 15)) + list(range(16, 41))],
    "BRONX": [f"104{n}" for n in range(51, 76)],
    "BROOKLYN": [f"112{n:02d}" for n in range(1, 40)],
    "QUEENS": [f"111{n:02d}" for n in range(1, 7)] + [f"113{n}" for n in range(54, 80)] + [f"114{n:02d}" for n in range(1, 37)],
    "STATEN ISLAND": [f"103{n:02d}" for n in range(1, 15)],
}
BOROUGH_BOX = {  # lat_min, lat_max, lon_min, lon_max
    "MANHATTAN": (40.70, 40.88, -74.02, -73.91), "BRONX": (40.79, 40.91, -73.93, -73.77),
    "BROOKLYN": (40.57, 40.74, -74.04, -73.83), "QUEENS": (40.54, 40.80, -73.96, -73.70),
    "STATEN ISLAND": (40.50, 40.65, -74.26, -74.05)}
BOROUGH_W = {"MANHATTAN": .2, "BRONX": .2, "BROOKLYN": .3, "QUEENS": .22, "STATEN ISLAND": .08}
ZIP_PREFIX_BOROUGH = {"100": "MANHATTAN", "101": "MANHATTAN", "102": "MANHATTAN", "104": "BRONX", "112": "BROOKLYN",
                      "103": "STATEN ISLAND", "110": "QUEENS", "111": "QUEENS", "113": "QUEENS", "114": "QUEENS", "116": "QUEENS"}
CLOSED_STATUS = {"Closed"}
OPEN_STATUS = {"Open", "Pending", "In Progress", "Assigned", "Started"}
