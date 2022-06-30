# Find duplicate files and create links

This simple python script looks for duplicates of files from the source path in the destination path and replaces them with a symlink pointing to the correct file in the source directory. Only links individual files, no folders.

By default it uses speculative caching that increases performance on previously seen files (identified by filename+filesize), in rare instances this may lead to errors so consider deactivating it if your use case includes multiple files with the same name (and potentially same size).

## Installation

Download the script (or use git clone).
No dependencies outside the standard library.
Uses python3, not tested with python2.

## Use

`find_duplicates.py [options] source destination`

By default a dry-run (no-changes to destination) is started. Use `--softlink` or `--hardlink` to replace duplicates in destination with a link to the corresponding file in the source directory.

```
find_duplicates.py [-h] [--softlink] [--hardlink] [--follow-symlinks] [--no-cache] [-d] [-v] source destination


positional arguments:
  source             Path of file or folder that serves as source for linking.
  destination        Path of file or folder that serves as target for linking.

options:
  -h, --help         show this help message and exit
  --softlink         Create softlinks. Without specifying soft- or hardlinks the script does just a dry-run.
  --hardlink         Create hardlinks. Without specifying soft- or hardlinks the script does just a dry-run.
  --follow-symlinks  Set this to follow symlinks, can result in redundant work or problems. Default: false
  --no-cache         Deactivate caching based on filename-filesize combination. Caching can cause problems, but improves speed immensely for repeated
                     executions
  -d, --debug        Print lots of debugging statements
  -v, --verbose      Be verbose
  ```

  ## Example

  Let's say you use a torrent client and have data on multiple drives. With the torrent directory being `/home/user/rtorrent/complete/`and most of your data being stored on `/mnt/disk1/content/`, `/mnt/disk2/content` etc.

  You download something via the torret client and copy it onto the corresponding disk and potentially rename the files on the disk (looking at you, sonarr). Now you want to free up space on your system drive but still want to seed the torrent. By running `python3 find_duplicates.py /mnt/disk1/content/ /home/user/rtorrent/complete/` the script will calculate the corresponding hashes for all files in both directories and look for matches. It is a dry-run, nothing will be changed. If you are happy with the proposed changes run the command again but add `--softlink` to create symbolic links (hardlinks do not work across different drives). Then run the same command for `disk2` etc.