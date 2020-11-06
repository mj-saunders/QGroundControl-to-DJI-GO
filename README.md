## Why?

QGroundControl is great! It's open source and provides the ability to easily
produce "survey" flight paths, which often costs a lot of money to achieve
via other apps and software.

Unfortunately it does not work with DJI drones.
Some great looking work has been done with https://github.com/diux-dev/rosettadrone
which seems to provide this capacity.
I have not tested it, but looks cool.

For one reason or another, I decided to just use the flight plan output from
QGroundControl and wrangle it into a shape that DJI GO 4 is happy with.
This way I can use the stock DJI app for now, until I have tested, and am
comfortable that the `rosettadrone` approach is stable for my uses.

And I get to save masses of time with survey-type waypoints :D


## Description

Convert QGroundControl survey waypoints to DJI GO 4 waypoints 2.0.
This is spefically intended to work _only_ with the "survey" mode from
QGroundControl.

This will likely only work if your smartphone is rooted, as you will need `su`.
My personal recommendation is to get `Magisk` installed.

This script is largely very naiive. It works as expected with `qgroundcontrol
v4.0.11-1` and `DJI GO 4 v??` as of date 06-11-2020.

There is no guarantee it will continue to work with future updates of either
application. You have been warned.

By default, a backup of the original DJI GO 4 database is made, so even if
the resulting db is broken, you can always recover the original.

Has only been tested using `omnirom beryllium` - your mileage may vary.


## Dependencies

For the script:
- Python 3
  - all required modules are I believe part of python core
- sqlite3

Obviously:
- QGroundControl
- DJI GO 4


## Prerequisite

- Open QGroundControl
  - either with the app on your phone, or more easily with the
desktop version. Tested with Linux and the App, but should be the same for Mac
and Windoze
- Create a survey waypoint mission
- Make sure the camera lens settings are all correct
- Use your common sense to determine
  - suitable overlap
  - cruising flight speed
  - suitable altitude
  - other?

Some settings can be passed directly to the script from the commandline, and
will overwrite the equivalent values from QGroundControl.

*n.b.* This script currently ignores takeoff and landing points, and solely focusses
on the survey mission waypoints, at a single altitude.


## Preparation

It is assumed that you have a terminal open on your "host" in a suitable working
directory, and that `qgc2dji.py` is in that directory.
When copying the `.db` you can store it wherever you like - it just has to be a
location that `adb pull` can retrieve from.
Once your phone is rooted and reasonably under your own control (developer
options enabled, USB debugging enabled):


## Usage

Use your own judgement when it comes to `chown` and `chmod` to match the original
`.db`

```
[host]$ adb shell

[phone]$ su
[phone]# cp /data/data/dji.go.v4/databases/way_point_2.db /sdcard/
[phone]# <ctrl-d>
[phone]$ <ctrl-d>

[host]$ adb pull /sdcard/way_point_2.db ./
[host]$ python ./qgc2dji.py -i <qgroundcontrol savefile> -d ./way_point_2.db
[host]$ adb push ./way_point_2.db /sdcard/
[host]$ adb shell

[phone]$ su
[phone]# cd /data/data/dji.go.v4/databases
[phone]# mv /sdcard/way_point_2.db ./
[phone]# ls -ld
drwxrwx--x 2 <user> <group> 4096 2020-11-06 11:48 .

[phone]# chown <user>:<group> ./way_point_2.db
[phone]# chmod 660 ./way_point_2.db
```


## Future

- Also update 'way_point_2_cache.db'
- Choice of "action upon mission completion"
  - Currently defaults to hover
- Altitude per waypoint
- Takeoff and landing points?
- Calculate appropriate crusing flight speed?
  - Dependent on required overlap and limitation of camera regarding photo
    interval
- Waypoint triggers (start/stop recording, take photo, etc)
