#! /usr/bin/python3
# Copyright (c) 2016 Norbert Kiesel <nk@iname.com>

#
# Updates the CSV file from the weekly updated NOAA list.
#

import xml.etree.ElementTree as ET
import re
import csv
import requests
from bs4 import BeautifulSoup

# input and output file
csvfile = '../San_Francisco.csv'

# updated NOAA list in XML format
noaa_url = 'https://www.navcen.uscg.gov/sites/default/files/xml/lightLists/weeklyUpdates/v6d11WeeklyChanges.xml'

# YRA Buoy page
yra_url = 'http://yra.org/descriptionofmarks/'

headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

noaa_coord_pattern = re.compile('(\d+)-(\d+)-(\d+.\d+) ?([NSEW])')
name_pattern = re.compile('.+ (\d+)$')
num_pattern = re.compile('^\[(\d+)\]')
dual_color_pattern = re.compile('^(\w)\w+ and (\w)\w+ ')
single_color_pattern = re.compile('^(Red|Yellow|Green|White)')
buoy_status_pattern = re.compile(r'<strong>(\w+)</strong>\D+(\d+) ([\d.]+)\D+(\d+) ([\d.]+) \((.+)\)')
whitespace_pattern = re.compile(r'\s+')
yra_coord_pattern = re.compile('(\d+) (\d+.\d+) / (\d+) (\d+.\d+)')

common_names = {
    "YRA-12": "Little Harding",
    "YRA-18": "Blossom Rock",
    "YRA-PB": "Point Bonita",
    "YRA-SF": "Lightship",
}

# convert DMS into a decimal
def dms2decdeg(d, m, s, c):
    seconds = float(d) * 3600 + float(m) * 60 + float(s)
    if c in ['S', 'W']:
        seconds = -seconds
    return "{:.6f}".format(seconds / 3600)

# convert DMM into a decimal
def dmm2decdeg(d, m, c):
    seconds = float(d) * 3600 + float(m) * 60
    if c in ['S', 'W']:
        seconds = -seconds
    return "{:.6f}".format(seconds / 3600)

# convert DMS into a decimal
def conv(n):
    match = noaa_coord_pattern.match(n)
    return dms2decdeg(match.group(1), match.group(2), match.group(3), match.group(4))

# convert YRA into a decimal
def yra_conv(n):
    match = yra_coord_pattern.match(n)
    if match:
        return [dmm2decdeg(match.group(1), match.group(2), 'N'), dmm2decdeg(match.group(3), match.group(4), 'W')]
    else:
        return None

# returns stripped text of child node named `tag`
def text(e, tag):
    text = e.findtext(tag)
    if text:
        return whitespace_pattern.sub(' ', text.strip())
    else:
        return None

# returns color abbreviation from either structure of light description
def color(c, s):
    color = dual_color_pattern.match(s)
    if color:
        color = color.group(1) + color.group(2)
    else:
        color = single_color_pattern.match(s)
        if color:
            color = str(color.group(1)[0])
        elif c:
            color = c.split()
            if color:
                color = str(color[1][-1])

    if color:
        color = color.upper()
        if color[0] in ['R', 'G', 'Y', 'W']:
            return "{} ".format(color)
    return ''

# returns description in our own format
def description(yra, nr, name, characteristic, structure):
    n = name_pattern.match(name)
    num = "'{}' ".format(n.group(1)) if n else ''
    col = color(characteristic, structure)
    cha = "{} ".format(characteristic) if characteristic else ''
    c = common_names.get(yra)
    com = " - {}".format(c) if c else ''
    return '[{}] {}{}{}{}{}'.format(nr, col, num, cha, name, com)


# contains mapping from NOAA light number to YRA name
noaa = {}

# set of all marks with NOAA light numbers
has_noaa_light_number = set()

# cotains mapping from YRA names to mark record/array
marks = {}

# contains YRA names in correct order
order = []

# read file and fill `noaa` and `marks`
with open(csvfile) as sffile:
    sf = csv.reader(sffile)
    # skip header
    next(sf)
    for row in sf:
        id = row[2]
        order.append(id)
        num = num_pattern.match(row[3])
        if num:
            noaa[num.group(1)] = id
            has_noaa_light_number.add(id)
        else:
            marks[id] = row

# use coordinates from YRA "buoy status page" unless mark has a NOAA light number
yra_count = 0

def ytext(n):
    return n.text.strip()

def yra(name, coords, desc):
    global yra_count
    if name == 'D':
        yraname = 'YRA-DOC'
    elif name == 'KKMI 6':
        yraname = 'YRA-6'
    else:
        yraname = "YRA-{}".format(name)
    coords = yra_conv(coords)
    # print("YRA name: {} coords: {}, description: {}".format(yraname, coords, desc))
    # print("found mark {} in YRA".format(yraname))
    yra_count += 1
    if coords and yraname not in has_noaa_light_number:
        # print("found mark {} in YRA but not in NOAA".format(yraname))
        existing = marks.get(yraname)
        lat = coords[0]
        lon = coords[1]
        if existing:
            marks[yraname] = [lat, lon, yraname, existing[3]]
        else:
            print("Mark {} at {} {}  is in the YRA Buoy status list but not in our CSV file".format(yraname, lat, lon))
       


with requests.get(yra_url, headers=headers) as html:
    soup = BeautifulSoup(html.text, 'html.parser')
    rows = soup.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) == 3:
            if ytext(cols[0]).startswith('Svenson'):
                bn = [ytext(x) for x in cols[0].find_all('p')]
                bc = [ytext(x) for x in cols[1].find_all('p')]
                for idx, n in enumerate(bn):
                    yra(n, bc[idx], "Olympic Circle {}".format(n[0]))
            else:
                yra(ytext(cols[0]), ytext(cols[1]), ytext(cols[2]))

# download and parse updated NOAA list and append required marks to `marks`
noaa_count = 0
with requests.get(noaa_url, headers=headers) as xml:
    xml.encoding = 'utf-8'
    for e in ET.fromstring(xml.text).find('dataroot'):
        llnr = text(e, 'LLNR')
        yraname = noaa.get(llnr)
        if yraname:
            noaa_count += 1
            # print("found mark {}[{}] in NOAA".format(yraname, llnr))
            marks[yraname] = [
                conv(text(e, 'Position_x0020__x0028_Latitude_x0029_')),
                conv(text(e, 'Position_x0020__x0028_Longitude_x0029_')),
                yraname,
                description(yraname, llnr, text(e, 'Aid_x0020_Name'), text(e, 'Characteristic'), text(e, 'Structure'))]

# replace csvfile content with updated marks
with open(csvfile, mode="w", newline='\r\n') as sffile:
    print('Latitude,Longitude,Name,Description', file=sffile)
    for id in order:
        d = marks[id]
        # This will create broken content if the description contains a "
        print('{},{},"{}","{}"'.format(*d), file=sffile)

print("Found {} marks in YRA and {} marks in NOAA".format(yra_count, noaa_count))
