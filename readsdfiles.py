# rmc file release number
dbname='mclark'

import xml.etree.ElementTree as ET
import psycopg2 as psql
from psycopg2.extensions import AsIs
import glob
import gzip
import os
import sys
import time
from pathlib import Path

# for rdkit Mol to Smiles
from rdkit import Chem
from rdkit import RDLogger
import hashlib

global hashset
global insertcache
index = 0

CHUNKSIZE = 50000
TEST_MODE = False
# controls whether storing original SD file.  This might be good if the conversion to smiles failed
# but it won't be searchable by structure anyway in this case.
STORE_SDFILE = False

hashset = set()
insertcache = set()
lastline = None
counts = {}
counts['molecule'] = 0
counts['other'] = 0


def readnextSDfile(file, conn):

    sdfile = ''
    active = True
    tags = {}
    blankcount = 0

    while active:
        line = file.readline()
        if line == '':
            blankcount += 1
            if blankcount > 3:
                return None

        sdfile += line
        if line.startswith('M  END'):
            active = False

    active = True
    while active:
        line = file.readline()
        if line.startswith('$$$$'):
            active = False
            break
        if line.startswith('>'):
            data = ''
            tag = line.strip()[8:-1]
            reading = True
            while reading:
              d = file.readline()
              if d.strip()  == '':  # data can be multi-line
                 reading = False
                 break 
              data += d[:-1]
            tags[tag] = data

    if STORE_SDFILE:
       tags['sdfile'] = sdfile

    smiles = ''


    if tags['XRN'] != '21291617':  # this one molecule crashes
        smiles = createSmiles(sdfile)

    tags['smiles'] = smiles
    tags['rx_file_id'] = index; # tag the file this came from for debugging

    if 'RIGHT' in tags.keys():
        del tags['RIGHT']  # copyright

    return tags


# centralize this function
def createSmiles(molblock):

    smiles = ''
    mol = None

    if molblock is None or molblock == '':
        return smiles
    try:
        mol = Chem.MolFromMolBlock(molblock, strictParsing=False, sanitize=True)
        if mol is not None:
            smiles = Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)

    except:
        pass

    return smiles

def initdb(conn):

    with open('../SFFLoader/sff_schema', 'r') as f:
        sql = f.read()

    print('initializing reaxys.sff')
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def indexdb(conn):
    with open('../SFFLoader/sff_index', 'r') as f:
        sql = f.read()

    print('indexing reaxys.sff')
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def readsdfile(fname, conn):

    """ read all of the individual SDFiles from the concatenated SDFile """
    print('readrdfiles: ', fname)
    lg = RDLogger.logger()
    lg.setLevel(RDLogger.CRITICAL)
    count = 0
    sql = 'insert into reaxys.sff (%s) values %s;'

    with gzip.open(fname, 'rt') as file:
        # loop over concatenated files
        while True:
            sdfrecord = readnextSDfile(file, conn)
            if sdfrecord is None:
                break;
            writerecord(conn, sql, sdfrecord)  

    flush(conn)

def writerecord(conn, sql, data):

     """ write a SDFile record the database """
     global hashset
     global insertcache
     rectype = None     
     count = 0
    
     with conn.cursor() as cur:
         columns = data.keys()
         values = [data[column] for column in columns]
         cmd = cur.mogrify(sql, (AsIs(','.join(columns)), tuple(values))).decode('utf-8')
         if TEST_MODE:
            print("--start record")
            print(cmd)
            print("--end record")
         
         if 'XRN' in columns:
            hashdata = data['XRN']
            rectype = 'molecule'
         else:
            hashdata = 'o'+ cmd
            rectype = 'other'


         if hashdata in hashset:
            print('** duplicate xrn', hashdata)

         hashset.add(hashdata)
         insertcache.add(cmd)
         count += 1
         counts[rectype] += 1
         if len(insertcache) > CHUNKSIZE:
             if not TEST_MODE:
                flush(conn)


     return count


def flush(conn):
  """ flush the data cache to the database """
  global insertcache

  if (TEST_MODE):
      print('flushed cache of ', len(insertcache) )

  statement = '\n'.join(insertcache)
  with conn.cursor() as cur:
      if len(statement) > 1:
        cur.execute(statement)

  conn.commit()
  insertcache.clear()


def getConnection():
    conn=psql.connect(user=dbname)
    return conn

            
def readsdfiles():
  """ read the SDFiles. This requires special functions because this is
    not an XML file
  """
  global insertcache
  global index

  conn = getConnection()
  initdb(conn)

  path = Path('.')
  version = os.path.basename(path.parent.absolute())
  print('loading version', version)
 
  with conn.cursor() as cur:
   cur.execute('insert into reaxys.sff_version (version) values (%s);', (version,))
   conn.commit()

  key = "_"
  numfiles = len(glob.glob('*.sdf.gz'))

  for i, filepath in enumerate(glob.iglob('*.sdf.gz')):
        start = time.time()
        index = os.path.basename(filepath)
        index = int(index[index.find(key) + len(key):-7 ])
        print('file index', index)
        oldlen = len(hashset)
        readsdfile(filepath, conn)
        newlen = len(hashset)
        new = newlen - oldlen
        elapsed = time.time() - start 
        remaining = '%5.2f' % ((numfiles-i-1)*elapsed )
        elapsed = "%5.2f" %(elapsed)
        print('\ttook:',elapsed, 'remaining:', remaining, 'inserts:',counts, ' new: ', new)
  
  conn.commit()

  indexdb(conn)
  conn.close()


readsdfiles()
print("complete")
