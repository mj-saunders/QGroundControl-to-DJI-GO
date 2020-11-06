#!/usr/bin/python3

# Convert QGroundControl survey waypoints to DJI GO 4 waypoints 2.0
#
# Solely for the creation of terrain survey mapping
# at a fixed altitude.

import sys
import os
import shutil
import argparse
import time
import math
import random
import sqlite3
import json


####### Globals ################################################################

mission_table = 'dji_pilot_dji_groundstation_waypoint2_model_WayPoint2MissionDBModel'
waypoint_table = 'dji_pilot_dji_groundstation_waypoint2_model_WayPoint2MissionDBModel$WayPoint2DBPoint'


####### Helper Function(s) #####################################################

def haversine(coord1, coord2):
    R = 6371000 #6372800  # Earth radius in meters [looks like DJI GO 4 uses 6371000]
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


################################################################################


# TODO: Confirm that 'complexItemType' = "survey"
# TODO: Also update 'way_point_2_cache.db'
#       - delete existing cached mission, and its' waypoints
#       - insert the same new data as with 'way_point_2.db'

parser = argparse.ArgumentParser(description='Convert QGroundControl survey waypoints to DJI GO 4 waypoints 2.0')

parser.add_argument('-d', '--dbfile', required=True, type=str,
        help='DJI GO 4 database file')
parser.add_argument('-i', '--infile', required=True, type=argparse.FileType('r'),
        help='JSON input file')
parser.add_argument('-a', '--altitude', type=float,
        help='Altitude above ground, in meters')
parser.add_argument('-f', '--finishaction', type=int, default=4,
        help='Act to perform upon mission completion [0, 1, 2, 3 or 4 - hover] (default: %(default)s)')
parser.add_argument('-n', '--name', type=str,
        help='Name for the mission (qgc2dji-survey_<date-time>)')
parser.add_argument('-s', '--speed', type=float,
        help='Flight speed')

args = parser.parse_args()

if not os.path.isfile(args.dbfile):
    print("[ERROR] Database file does not exist!", file=sys.stderr)
    exit(2)

try:
    conn = sqlite3.connect(args.dbfile)
except sqlite3.Error as e:
    print("[ERROR] Could not connect to database!\n" + e.args[0], file=sys.stderr)
    exit(2)


# The only values we care about are inside "TransectStyleComlexItem"
items = json.loads(args.infile.read())['mission']['items']

main_data = None
for item in items:
    if 'TransectStyleComplexItem' in item:
        main_data = item["TransectStyleComplexItem"]
        break
if not main_data:
    print("[ERROR] Required data not present in json!", file=sys.stderr)
    exit(2)

altitude = args.altitude
if not altitude:
    altitude = main_data["CameraCalc"]["DistanceToSurface"]

finishaction = args.finishaction

# If this is no set, it will be later on during parsing
flight_speed = args.speed
if not flight_speed:
    # First check if a value was set in the json
    for item in items:
        if 'command' in item and item['command'] == 178:
            # Reverse-engineered this location - could easily change in future QGroundControl releases
            flight_speed = item['params'][1]
            break
# Set an acceptable, but slow default if speed still hasn't been set
# TODO: Calculate this based on mission distance / photo count / 5s to get one photo per 5seconds ???
if not flight_speed:
    flight_speed = 3.5

mission_name = args.name
if not mission_name:
    timestr = time.strftime('%d%m%Y-%H%M%S')
    mission_name = "qgc2dji-survey_" + timestr

# DJI GO database stores time in milliseconds since epoch
update_time = int(round(time.time() * 1000))


cur = conn.cursor()

cur.execute(f'SELECT missionId FROM {mission_table}')
existing_ids = cur.fetchall()

# Looking at existing database entries, it appears that 'missionId' is an arbitrary value
mission_id = random.randrange(10000,99999)
while (mission_id,) in existing_ids:
    print("[INFO] ID collision. Generating new ID.")
    mission_id = random.randrange(10000,99999)

waypoint_queue = []

# Set default values for DJI GO database waypoint table
heading_type = 0        # Free ?
poi_index    = -1       # None ?
heading      = 0        # Look-ahead ?
action       = 0        # Do nothing (as opposed to take photo, etc)
pitch        = -90.0    # Point camera toward ground
radius       = 2.0      # Some default ?  Could be realted to 'arc' vs 'polyline'
speed        = 0.0      # Use 'autoFlightSpeed' from 'mission_table'

# Prepare each waypoint for insert
waypoints = main_data['VisualTransectPoints']
last_coord = ()
curr_coord = ()
accum_distance = 0

# TEST DATA - Expected accumulated result: 1825.33557128906
# Result initially was 1825.8512451494107 which should be close enough
# Result with "standard" Earth radius is 1825.3355327088402 which is closer still
# TODO: Test geopy module ? [see: https://janakiev.com/blog/gps-points-distance-python/]
#waypoints = [(-19.9914615912953,57.6010317688705),
#                (-19.9906124706645,57.6018561685789),
#                (-19.9907586941667,57.6021400677547),
#                (-19.9917566018806,57.6012092059048),
#                (-19.9920208284113,57.6013183979067),
#                (-19.9908972216132,57.6023884794603),
#                (-19.9910049650248,57.6026669190904),
#                (-19.9923184032966,57.601438509184),
#                (-19.9925544106552,57.6017169485915),
#                (-19.9911050125569,57.6029944951315),
#                (-19.9912281477626,57.6033111519851),
#                (-19.9927904174512,57.6019353328111),
#                (-19.9931793793255,57.6022154786425),
#                (-19.9915212340617,57.6036721688515),
#                (-19.9915956280736,57.6039779066684),
#                (-19.9934298150556,57.6024819755698)]

count = 0
for waypoint in waypoints:
    latitude    = waypoint[0]
    longitude   = waypoint[1]
    waypoint_id = count
    count = count + 1

    waypoint_queue.append((heading_type, altitude, mission_id, poi_index, heading, latitude, action, pitch, radius, speed, longitude, waypoint_id))

    if count > 1:
        curr_coord = (latitude, longitude)
        accum_distance = accum_distance + haversine(last_coord, curr_coord)
        last_coord = curr_coord
    else:
        last_coord = (latitude, longitude)


# Set default values for DJI GO database mission table
is_use_custom_direction  = 0
first_lon                = 0.0
first_lat                = 0.0
local                    = ''#None  # becomes NULL in sqlite db
exit_mission_on_rc_lost  = 0        # Keep flying
flight_path_mode         = 0        # 'polyline' vs 'arc' ?
is_cache                 = 0        # ?
rotate_gimbal_pitch      = 1        # ?
goto_first_waypoint_mode = 0        # ?
repeat_times             = 1        # Only fly the mission once
max_flight_speed         = 8.3      # (m/s) Based on ~30km/h being a good maximum
heading_mode             = 0        # ? Different from 'heading_type' ?
is_enable_multi_poi      = 0
route_distance           = accum_distance #'' #None  # Can we get away with leaving this blank !?
point_count              = len(waypoints)


print("\n======= MISSION DATA =======\n")
print(f"Mission name:\t\t{mission_name}")
print(f"Mission id:\t\t{mission_id}")
print(f"Max flight speed:\t{max_flight_speed} m/s")
print(f"Cruise speed:\t\t{flight_speed} m/s")
print(f"Altitude:\t\t{altitude} m")
print(f"Route distance:\t\t{route_distance} m")
print(f"Finished action:\t{finishaction}")
print("")

# TODO: Implement more robust regex version of the following
proceed = ''
while proceed not in ['y', 'Y', 'n', 'N']:
    proceed = input("Write out to database? [y/n] ")

if proceed == 'n' or proceed == 'N':
    print("[INFO] Exiting without updating database.")
    exit(1)


# Generate SQL INSERT for the mission
sql = (f"INSERT INTO {mission_table}"
       "(missionId, isUseCustomDirection, updateTime, finishedAction, firstLng, local, "
       "exitMissionOnRCSignalLost, flightPathMode, isCache, rotateGimbalPitch, "
       "gotoFirstWaypointMode, pointCount, repeatTimes, routDistance, firstLat, "               # n.b. 'routDistance' is not a spelling mistake
       "missionName, maxFlightSpeed, headingMode, autoFlightSpeed, isEnableMultiPOI) "
       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
cur.execute(sql, (mission_id, is_use_custom_direction, update_time, finishaction,
                first_lon, local, exit_mission_on_rc_lost, flight_path_mode,
                is_cache, rotate_gimbal_pitch, goto_first_waypoint_mode, point_count,
                repeat_times, route_distance, first_lat, mission_name, max_flight_speed,
                heading_mode, flight_speed, is_enable_multi_poi))

# SQL INSERT for all waypoints from QGroundControl
sql = (f"INSERT INTO {waypoint_table}"
       "(headingType, altitude, missionId, poiIndex, heading, latitude, action, "
       "pitch, radius, speed, longitude, myIndex) "
       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")
cur.executemany(sql, waypoint_queue)


# TODO: Implement database backup as a commandline option
shutil.copy2(args.dbfile, args.dbfile + ".bak")


# Write changes back to the database
conn.commit()


# TODO: Determine if there is any other clean up


conn.close()
