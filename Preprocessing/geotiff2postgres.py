#!/usr/bin/env python
# -*- coding: utf-8 -*-
## @file
# Convert an input (Geo)TIFF file to ESRI data. It works on Python2, but it might give errors on Python3.
# Assumptions: There is a folder Bravo/Preprocessing/data where snappy files will be saved.
# Usage: ./geotiff2postgres.py <tiff file> <postgres user>

import sys
import snappy
import numpy as np

from psycopg2 import connect
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pg import DB
from base64 import b64encode
from osgeo import gdal
from scipy.misc import imresize
from skimage.transform import downscale_local_mean
from scipy.special import expit
from skimage.filters.rank import median
from skimage.morphology import disk

def store_img(_id, x, y, data):
    """
        Compress each tile into a snappy file and insert it as a new record in the data table.
    """
    compressed_data = snappy.compress(data.tobytes())

    sql = 'INSERT INTO data (id, row, col, data) VALUES (%d, %d, %d, decode(\'%s\', \'base64\'))'
    sql = sql % (_id, y, x, b64encode(compressed_data))

    # write the data out to file too, so that we don't have to recompute it all
    with open('data/(%d, %d).snappy' % (x, y), 'wb') as f:
        f.write(compressed_data)
    db.query(sql)

def check_database(db_name, db_user):
    """
        Check if database grpproj exists and create it if it doesn't
    """
    ## Set connection to the default postgres database
    # How to instantiate it depends on how PostgreSQL was installed
    # Alternative: con = connect(dbname='postgres', user=db_user, host='localhost')
    con = connect(dbname='postgres', user=db_user, host="/tmp/")
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute( "SELECT EXISTS(SELECT FROM pg_catalog.pg_database WHERE lower(datname) = lower(%s))",(db_name,))
    if not cur.fetchone()[0]:
        cur.execute('CREATE DATABASE ' + db_name)
    con.commit()
    con.close()

def check_table(db_name, table_name, db_user):
    """
        Check if table data exists in database grpproj and create it if it doesn't
    """
    ## Set connection to the grpproj database
    # How to instantiate it depends on how PostgreSQL was installed
    # Alternative: con = connect(dbname=db_name, user=db_user, host='localhost')
    con = connect(dbname=db_name, user=db_user, host="/tmp")
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute("select exists(select * from information_schema.tables where table_name=%s and table_catalog=%s)", (table_name,db_name,))
    if not cur.fetchone()[0]:
        cur.execute("CREATE TABLE IF NOT EXISTS data ( id integer, row integer, col integer, data bytea )")
    con.commit()
    con.close()

def test_empty(db_name, db_user):
    """
        Check that table is empty before starting to insert 
    """
    ## Set connection to the grpproj database
    # How to instantiate it depends on how PostgreSQL was installed
    # Alternative: con = connect(dbname=db_name, user=db_user, host='localhost')
    con = connect(dbname=db_name, user=db_user, host="/tmp")
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute("SELECT count(*) from data;")
    
    ## @test Check that there are no records in data table
    assert cur.fetchone()[0] == 0

img = gdal.Open(sys.argv[1])
data = np.array(img.GetRasterBand(1).ReadAsArray())
data = downscale_local_mean(data, (10, 10))
data = data.astype(np.uint16)

ridge = 20
mountain = 50
data[data <= ridge] /= 2
data[(data > ridge) & (data < mountain)] += 250
data = median(data, disk(10))
data = data.astype(np.uint16)

width, height = data.shape

# Python Geospatial Development Essentials (page 36: GeoTIFF)
## Width and height of a tile.
box_size = 128

## The user of the PostgreSQL database is given as an argument
db_user = sys.argv[2]
## The database name must be grpproj
db_name = 'grpproj'
## The table name must be data
table_name = 'data'

check_database(db_name, db_user)
check_table(db_name, table_name, db_user)

## Database in which data from the .tiff file will be stored
db = DB(dbname='grpproj', host='localhost', user=db_user)

## @test Check that db was assigned to a database
assert db is not None

clean_sql = 'DELETE FROM data'
db.query(clean_sql)

test_empty(db_name, db_user)

_id = 0
# Break down the image into (up to) 500px*500px chunks
for x in range(0, width, box_size):
    for y in range(0, height, box_size):
        frame_width = min(width - x, box_size)
        frame_height = min(height - y, box_size)

        frame_data = data[x:x+frame_width,y:y+frame_height]
        if np.count_nonzero(frame_data) >0:
            store_img(_id, x, y, frame_data)
            _id = _id + 1
