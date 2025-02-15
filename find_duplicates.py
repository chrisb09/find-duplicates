#!/bin/python3
import argparse
import os
import hashlib
import logging
import math
import pickle
import json
import time
from datetime import timedelta

def migrate_database():
  if not os.path.exists(hash_file_path):
    if os.path.exists(hash_file_path_legacy):
      migrate = ""
      while migrate != "y" and migrate != "n":
        migrate = input("Unmigrated pickle file found. Do you wish to migrate it? (y/n): ").lower()
      if migrate == "n":
        print("Support for the old cache format has been dropped. Migration is necessary.")
        exit()
      legacy_data = load_hashes_legacy(hash_file_path_legacy)
      changed_data = dict()
      
      # json cannot use tuples as keys so we use a string
      for key in legacy_data:
        basename, filesize = key
        new_key = f"{filesize} {basename}"
        changed_data[new_key] = legacy_data[key]
      # previously, only sha1 was supported, so it follows that all hashes in the pickle file are sha1 hashes
      data = {"sha1": changed_data}
      save_hashes(hash_file_path, data)
      
      print("renaming legacy pickle file")
      os.rename(hash_file_path_legacy, os.path.join(directory, "hashes_legacy.p"))

def main():
  parser = argparse.ArgumentParser(description='Find duplicate files in destination of files in source,'+
            'delete destination file and replace it with a link originating from the corresponding source file.')
  
  parser.add_argument('source', nargs='+', help='One or more paths to the source file or folder (the original location(s) of the files to be linked).')
    
  parser.add_argument('destination', help='Path to the destination file or folder (where symbolic links will be created, pointing to the source).')

  parser.add_argument('--softlink', dest='softlink', action='store_true',
                      help='Create softlinks. Without specifying soft- or hardlinks the script does just a dry-run.')

  parser.add_argument('--hardlink', dest='hardlink', action='store_true',
                      help='Create hardlinks. Without specifying soft- or hardlinks the script does just a dry-run.')

  parser.add_argument('--follow-symlinks', dest="follow_symlinks", action='store_true',
                      help='Set this to follow symlinks, can result in redundant work or problems. Default: false')
  
  parser.add_argument('--dont-ignore-hardlinks', dest="dont_ignore_hardlinks", action='store_true',
                      help='Set this to not ignore hardlinks. Default: false')

  parser.add_argument('--no-cache', dest="no_cache", action="store_true",
                      help="Deactivate caching based on filename-filesize combination. Caching can cause problems, but improves speed immensely for repeated executions")

  parser.add_argument('--no-source-cache', dest="no_source_cache", action="store_true",
                      help="Deactivate caching based on filename-filesize combination for the source directory.")

  parser.add_argument('--no-destination-cache', dest="no_destination_cache", action="store_true",
                      help="Deactivate caching based on filename-filesize combination for the destination directory.")

  parser.add_argument('--print-hashes', dest="print_hashes", action="store_true",
                      help="Prints list of all files for debugging purposes.")
  
  
  group = parser.add_mutually_exclusive_group()

  hash_function = None

  group.add_argument('--sha1', dest=hash_function, action='store_const', const=hashlib.sha1, help='Use sha1 hashes (default)')
  group.add_argument('--sha256', dest=hash_function, action='store_const', const=hashlib.sha256, help='Use sha256 hashes')
  group.add_argument('--sha512', dest=hash_function, action='store_const', const=hashlib.sha512, help='Use sha512S hashes')
  group.add_argument('--md5', dest=hash_function, action='store_const', const=hashlib.md5, help='Use md5 hashes')

  parser.add_argument(
      '-d', '--debug',
      help="Print lots of debugging statements",
      action="store_true"
  )
  parser.add_argument(
      '-v', '--verbose',
      help="Be verbose",
      action="store_true"
  )
  args = parser.parse_args()
  
  if args.debug:
      loglevel = logging.DEBUG
  elif args.verbose:
      loglevel = logging.INFO
  else:
      loglevel = logging.WARNING
  
  for handler in logging.root.handlers[:]:
      logging.root.removeHandler(handler)
  logging.basicConfig(level=loglevel)
  logging.info("args.verbose: %s", str(args.verbose))
  logging.info("Set log level to: %s", str(loglevel))
  logging.info("Log Level: %s", logging.getLevelName(logging.getLogger().getEffectiveLevel()))
  follow_symlinks = args.follow_symlinks
  softlink = args.softlink
  hardlink = args.hardlink
  if hash_function is None:
    hash_function = hashlib.sha1
  hash_function_name = hash_function.__name__[8:]
  if not hash_function_name in hashes:
    hashes[hash_function_name] = dict()

  if softlink and hardlink:
    print("Cannot create soft- and hardlinks at the same time. Choose one.")
    exit()

  use_source_cache = (not args.no_cache) and (not args.no_source_cache)
  use_destination_cache = (not args.no_cache) and (not args.no_destination_cache)

  print("-"*40)
  print("Use Cache: "+str(not args.no_cache))
  print("Use source cache: "+str(use_source_cache))
  print("Use destination cache: "+str(use_destination_cache))
  print("-"*40)

  source_files = get_all_files(args.source, ignore_softlinks=not args.follow_symlinks, ignore_hardlinks=False)
  destination_files = get_all_files(args.destination, ignore_softlinks=not args.follow_symlinks, ignore_hardlinks=not args.dont_ignore_hardlinks)

  source_hashes = dict()      # hash: abspath
  destination_hashes = dict() # hash: abspath
  
  source_files_unhashed_size = sum(map(lambda x: safe_file_size(x), filter(lambda x: (not has_file_hash(x, hash_function_name)) or (not use_source_cache), source_files)))
  source_files_hashed_size = 0

  destination_files_unhashed_size = sum(map(lambda x: safe_file_size(x), filter(lambda x: (not has_file_hash(x, hash_function_name)) or (not use_destination_cache), destination_files)))
  destination_files_hashed_size = 0

  start_time = time.time()
  
  for sf in source_files:
    if not os.path.islink(sf) or follow_symlinks:
      add = (not has_file_hash(sf, hash_function_name)) or (not use_source_cache)

      hash = get_file_hash(sf, hash_function, use_source_cache)
      if add:
        source_files_hashed_size += safe_file_size(sf)
        time_used = (time.time() - start_time)
        time_left = (time_used / (source_files_hashed_size / source_files_unhashed_size)) - time_used
        print("Source-file hashed so far: " + ("%.2f"% (source_files_hashed_size/float(10**9) ) ) +
        "/" + ("%.2f"% (source_files_unhashed_size/float(10**9) ) ) +
        " GB (" + ("%.2f"% (source_files_hashed_size*100/source_files_unhashed_size) ) + "%)"+
        " avg. Speed: "+("%.2f"% (source_files_hashed_size / time_used / float(10**6))) + " MB/s"
        " ETA: "+calculate_elapsed_time(time_left))
      if hash is not None:
        source_hashes[hash] = os.path.abspath(sf)

  start_time = time.time()

  for df in destination_files:
    if not os.path.islink(df) or follow_symlinks:
      add = (not has_file_hash(df, hash_function_name)) or (not use_destination_cache)
      hash = get_file_hash(df, hash_function, use_destination_cache)
      if add:
        destination_files_hashed_size += safe_file_size(sf)
        time_used = (time.time() - start_time)
        time_left = (time_used / (destination_files_hashed_size / destination_files_unhashed_size)) - time_used
        print("Destination-file hashed so far: " + ("%.2f"% (destination_files_hashed_size/float(10**9) ) ) +
        "/" + ("%.2f"% (destination_files_unhashed_size/float(10**9) ) ) +
        " GB (" + ("%.2f"% (destination_files_hashed_size*100/destination_files_unhashed_size) ) + "%)"+
        " avg. Speed: "+("%.2f"% (destination_files_hashed_size / time_used / float(10**6))) + " MB/s"
        " ETA: "+calculate_elapsed_time(time_left))

      if hash is not None:
        destination_hashes[hash] = os.path.abspath(df)

  matches = []
  comm_match_filesize = 0

  if (args.print_hashes):
    print("-------------------")
    print("Source files: ")
    for sh in source_hashes:
      print("  "+str(source_hashes[sh])+":\n   "+str(sh)+"\n    "+str(os.path.getsize(source_hashes[sh])))
    print("-------------------")
    print("Destination files: ")
    for dh in destination_hashes:
      print("  "+str(destination_hashes[dh])+":\n   "+str(dh)+"\n    "+str(os.path.getsize(destination_hashes[dh])))

  timestamp_before_compare = time.time()
  for sh in source_hashes:
    for dh in destination_hashes:
      if sh == dh:
        file_size = os.path.getsize(source_hashes[sh])
        comm_match_filesize += file_size
        print("Match found: " + ("%.2f"% (file_size/float(10**9) ) ) + " GB")
        print("    '"+source_hashes[sh]+"'")
        print("--->'"+destination_hashes[dh]+"'")
        matches.append((source_hashes[sh], destination_hashes[dh]))
  print("Compared "+str(len(source_hashes))+" source files with "+str(len(destination_hashes))+" destination files in " + ("%.1f"% (time.time()-timestamp_before_compare))+"s")
  print("In total "+str(len(matches))+" Matches found with a total size of " + ("%.2f"% (comm_match_filesize/float(10**9) ) ) + " GB")
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

def save_hashes(file, data):
  if os.path.exists(file):
    logging.debug("Backing up old hashes")
    backup_path = os.path.join(directory, "hashes_backup.json")
    if os.path.exists(backup_path):
      os.remove(backup_path)
    os.rename(file, backup_path)
  logging.info("Saving hashes json to "+file)
  json.dump(data, open(file, 'w'))
  logging.debug("Saving complete.")

def save_hashes_legacy(file, data):
  logging.info("Saving hashes pickle to "+file)
  with open(file, 'wb') as fp:
    pickle.dump(data, fp, protocol=pickle.HIGHEST_PROTOCOL)
  logging.debug("Saving complete.")

def load_hashes(file):
  logging.info("Loading hash cache from json file.")
  return json.load(open(file, 'r'))
  
def load_hashes_legacy(file):
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

def calculate_elapsed_time(time_left):
    formatted_time = timedelta(seconds=time_left)
    print(formatted_time)
    # Splitting the components
#    days, hours, minutes, _ = formatted_time.split(":")
    days = formatted_time.days
    hours, remainder = divmod(formatted_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Create a list to store the non-zero components
    time_components = []

    # Add non-zero components to the list
    if days != 0:
        time_components.append(f"{days} days")
    if hours != 0:
        time_components.append(f"{hours} hours")
    if minutes != 0:
        time_components.append(f"{minutes} minutes")

    # Join the components into a human-readable string
    elapsed_time_str = ", ".join(time_components)

    return elapsed_time_str

def hash_file(file, hash_function=hashlib.sha1):
  try:
    filesize = os.path.getsize(file)
  except:
    return None
  if filesize <= 0:
    return None
  BUF_SIZE = 65536  # 64kb chunks
  parts = math.ceil(filesize / BUF_SIZE)
  logging.info("Reading file '"+file+"' in "+str(parts)+" parts.")
  hash_object = hash_function()

  counter = 0
  text = "'"+os.path.basename(file)+"' hash progress"

  progress_bar(counter, parts, text, bar_length=20)

  start_time = time.time()
  try:
    with open(file, 'rb') as f:
        while True:
          data = f.read(BUF_SIZE)
          if not data:
            break
          hash_object.update(data)
          if ((counter * 100 // parts) != ((counter+1) * 100 // parts)):
            progress_bar(counter, parts, text, bar_length=20)
          counter += 1
    end_time = time.time()
    print("Calculating " + hash_function.__name__[8:] + "hash of '"+os.path.basename(file)+"' took "+("%.1f" % (end_time-start_time))+" s. with avg. speed of "+("%.2f" % (os.path.getsize(file)/(end_time-start_time)/float(1<<20)))+" MB/s")
  except OSError as error:
    print("")
    print(error)
    print("")
    return None
  return hash_object.hexdigest()

def _file_size(file):
  return os.path.getsize(file)

def safe_file_size(file):
  try:
    return _file_size(file)
  except:
    return 0

def has_file_hash(file, hash_function_name):
  filesize = None
  try:
    filesize = _file_size(file)
  except Exception as e:
    print(e)
  if filesize is not None:
    basename = os.path.basename(file)
    key = f"{filesize} {basename}"
    return key in hashes[hash_function_name]
  return False

def get_file_hash(file, hash_function, use_cache):
  filesize = safe_file_size(file)
  basename = os.path.basename(file)
  key = f"{filesize} {basename}"
  hash_function_name = hash_function.__name__[8:]
  if use_cache and key in hashes[hash_function_name]:
    if hashes[hash_function_name][key] is not None:
      logging.info("Found file hash for "+str(key)+": "+hashes[hash_function_name][key])
    else:
      logging.info("Found None-hash for "+str(key))
    return hashes[hash_function_name][key]
  hash = hash_file(file, hash_function)
  #if use_cache:
  hashes[hash_function_name][key] = hash
  save_hashes(hash_file_path, hashes)
  if hash is not None:
    logging.info("Calculated file hash for "+str(key)+": "+hash)
  else:
    logging.info("Could not calculate hash.")
  return hash

def get_all_files(folder, ignore_softlinks=True, ignore_hardlinks=True):
  if type(folder) is list:
    return [file for f in folder for file in get_all_files(f, ignore_softlinks, ignore_hardlinks)]
  l = []
  ignored_softlinks = 0
  ignored_hardlinks = 0
  for path, subdirs, files in os.walk(folder):
    for name in files:
      # ignore hardlinks
      file_path = os.path.join(path, name)
      if os.path.islink(file_path) and (ignore_softlinks or not os.path.exists(file_path)):
        continue
      if ignore_hardlinks and os.stat(file_path).st_nlink > 1:
        ignored_hardlinks += 1
        continue
      l.append(file_path)
  logging.info("Found "+str(len(l))+" files in '"+folder+"'")
  logging.info("Ignored "+str(ignored_hardlinks)+" hardlinks.")
  return l




directory = os.path.dirname(os.path.realpath(__file__))

hash_file_path = os.path.join(directory, "hashes.json")
hash_file_path_legacy = os.path.join(directory, "hashes.p")

migrate_database()

if os.path.exists(hash_file_path):
  hashes = load_hashes(hash_file_path) # dict ( hash_function: dict( (name, size): hash))
else:
  hashes = dict()

logging.info("Loaded "+str(sum([len(hashes[name]) for name in hashes]))+" previously calculated hashes.")


if __name__ == "__main__":
  main()
