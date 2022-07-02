#!/bin/python3
import argparse
import os
import hashlib
import logging
import math
import pickle
import time

parser = argparse.ArgumentParser(description='Find duplicate files in destination of files in source,'+
          'delete destination file and replace it with a link originating from the corresponding source file.')

parser.add_argument('source',
                    help='Path of file or folder that serves as source for linking.')

parser.add_argument('destination',
                    help='Path of file or folder that serves as target for linking.')

parser.add_argument('--softlink', dest='softlink', action='store_true',
                    help='Create softlinks. Without specifying soft- or hardlinks the script does just a dry-run.')

parser.add_argument('--hardlink', dest='hardlink', action='store_true',
                    help='Create hardlinks. Without specifying soft- or hardlinks the script does just a dry-run.')

parser.add_argument('--follow-symlinks', dest="follow_symlinks", action='store_true',
                    help='Set this to follow symlinks, can result in redundant work or problems. Default: false')

parser.add_argument('--no-cache', dest="no_cache", action="store_true",
                    help="Deactivate caching based on filename-filesize combination. Caching can cause problems, but improves speed immensely for repeated executions")

parser.add_argument(
    '-d', '--debug',
    help="Print lots of debugging statements",
    action="store_const", dest="loglevel", const=logging.DEBUG,
    default=logging.WARNING,
)
parser.add_argument(
    '-v', '--verbose',
    help="Be verbose",
    action="store_const", dest="loglevel", const=logging.INFO,
)
args = parser.parse_args()
logging.basicConfig(level=args.loglevel)

dir = os.path.dirname(os.path.realpath(__file__))

follow_symlinks = args.follow_symlinks
softlink = args.softlink
hardlink = args.hardlink

if softlink and hardlink:
  print("Cannot create soft- and hardlinks at the same time. Choose one.")
  exit()

use_cache = not args.no_cache

hash_file_path = os.path.join(dir, "hashes.p")

def save_hashes(file, data):
  logging.info("Saving hashes pickle to "+file)
  with open(file, 'wb') as fp:
    pickle.dump(data, fp, protocol=pickle.HIGHEST_PROTOCOL)
  logging.debug("Saving complete.")

def load_hashes(file):
  logging.info("Loading hashes from pickle file "+file)
  with open(file, 'rb') as fp:
    data = pickle.load(fp)
    return data

def progress_bar(current, total, text, bar_length=20):
    fraction = current / total

    arrow = int(fraction * bar_length - 1) * '-' + '>'
    padding = int(bar_length - len(arrow)) * ' '

    ending = '\n' if current == total else '\r'

    print(f'{text}: [{arrow}{padding}] {int(fraction*100)}% {current}/{total}', end=ending)

def hash_file(file):
  file_size = os.path.getsize(file)
  if file_size <= 0:
    return None
  BUF_SIZE = 65536  # 64kb chunks
  parts = math.ceil(file_size / BUF_SIZE)
  logging.info("Hashing file '"+file+"' into "+str(parts)+" parts.")
  sha1 = hashlib.sha1()

  counter = 0
  text = "'"+os.path.basename(file)+"' hash progress"

  progress_bar(counter, parts, text, bar_length=20)

  start_time = time.time()
  with open(file, 'rb') as f:
      while True:
        data = f.read(BUF_SIZE)
        if not data:
          break
        sha1.update(data)
        if ((counter * 100 // parts) != ((counter+1) * 100 // parts)):
          progress_bar(counter, parts, text, bar_length=20)
        counter += 1
  end_time = time.time()
  print("SHA1 hash of '"+os.path.basename(file)+"' took "+("%.1f" % (end_time-start_time))+" s. with avg. speed of "+("%.2f" % (os.path.getsize(file)/(end_time-start_time)/float(1<<20)))+" MB/s")
  return sha1.hexdigest()

def file_size(file):
  return os.path.getsize(file)

def get_file_hash(file):
  fs = file_size(file)
  bn = os.path.basename(file)
  key = (bn, fs)
  if use_cache and key in hashes:
    logging.info("Found file hash for "+str(key)+": "+hashes[key])
    return hashes[key]
  hash = hash_file(file)
  if use_cache and hash is not None:
    hashes[key] = hash
    save_hashes(hash_file_path, hashes)
    logging.info("Calculated file hash for "+str(key)+": "+hash)
  return hash

def get_all_files(folder):
  l = []
  for path, subdirs, files in os.walk(folder):
    for name in files:
      l.append(os.path.join(path, name))
  logging.info("Found "+str(len(l))+" files in '"+folder+"'")
  return l

if use_cache and os.path.exists(hash_file_path):
  hashes = load_hashes(hash_file_path) #dict( (name, size), hash)
else:
  hashes = dict()

logging.info("Loaded "+str(len(hashes))+" previously calculated hashes.")

source_files = get_all_files(args.source)
destination_files = get_all_files(args.destination)

source_hashes = dict()      # hash: abspath
destination_hashes = dict() # hash: abspath

for sf in source_files:
  if not os.path.islink(sf) or follow_symlinks:
    hash = get_file_hash(sf)
    if hash is not None:
      source_hashes[hash] = os.path.abspath(sf)

for df in destination_files:
  if not os.path.islink(df) or follow_symlinks:
    hash = get_file_hash(df)
    if hash is not None:
      destination_hashes[hash] = os.path.abspath(df)

matches = []

for sh in source_hashes:
  for dh in destination_hashes:
    if sh == dh:
      print("Match found: " + ("%.2f"% (os.path.getsize(source_hashes[sh]) /float(10**9) ) ) + " GB")
      print("    '"+source_hashes[sh]+"'")
      print("--->'"+destination_hashes[dh]+"'")
      matches.append((source_hashes[sh], destination_hashes[dh]))
print("In total "+str(len(matches))+" Matches found.")
if softlink or hardlink:
  if softlink:
    print("Creating softlinks...")
  else:
    print("Creating hardlinks...")
  for source, destination in matches:
    os.unlink(destination)
    if softlink:
      os.symlink(source, destination)
    else:
      os.link(source, destination)
  print("Done.")
else:
  print("Dry-run done.")
  print("If you are happy with the dry-run use")
  print("  --softlink   to create softlinks")
  print("  --hardlink   to create hardlinks")
