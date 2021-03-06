#!/usr/bin/env python

# vim: expandtab tabstop=4 shiftwidth=4

from argparse import ArgumentParser
from datetime import datetime

import exifread
import logging
import os
import shutil
import sys

logging.basicConfig(level=logging.INFO)

min_datetime = datetime(2015, 1, 1)

def determine_capture_time(basename, extensions):
    capture_time = None
    possible_dates = ( get_date(basename+e) for e in extensions )
    possible_dates = ( dt for dt in possible_dates if dt is not None )
    possible_dates = [ dt for dt in possible_dates if dt > min_datetime ]

    if len(possible_dates) == 0:
        capture_time = None
    elif len(possible_dates) == 1:
        capture_time = possible_dates[0]
    else:
        capture_time = min(possible_dates)

    return capture_time

def get_date(file_path):
    exif_date = get_exif_date(file_path)

    if exif_date is not None:
        return exif_date

    return datetime.fromtimestamp(os.path.getmtime(file_path))

def get_exif_date(file_path):
    time_field = 'Image DateTime'

    with open(file_path, 'rb') as f:
        try:
            tags = exifread.process_file(f, details=False, stop_tag=time_field)

            if time_field in tags:
                return datetime.strptime(tags[time_field].values, '%Y:%m:%d %H:%M:%S')
            else:
                return None
        except Exception as e:
            logging.error(str(e))
            return None

def determine_output_dir(output_dir, dt, default_event):
    new_dir = dt.strftime('%Y.%m.%d')
    default_event = default_event.strip()

    if len(default_event) > 0:
        new_dir += '.' + default_event

    return output_dir + os.sep + new_dir

def make_output_dir(full_path, pretend=False):
    if not os.path.exists(full_path):
        logging.info('Making directory {0}'.format(full_path))

        if not pretend:
            os.mkdir(full_path, mode=0o755)

def make_name(prefix, dt):
    return prefix.strip() + dt.strftime('%Y%m%d%H%M%S')

def copy_file(from_path, to_path, pretend=False):
    logging.info('Copying {0} to {1}'.format(from_path, to_path))

    if not pretend:
        shutil.copy2(from_path, to_path)

def group_files(files):
    groups = {}

    for f in files:
        basename, ext = os.path.splitext(f)

        if basename not in groups:
            groups[basename] = set()

        if len(ext) > 0:
            groups[basename].add(ext)

    return groups

def transpose_dict(d):
    ret = {}

    for k, v in d.items():
        if v not in ret:
            ret[v] = set()

        ret[v].add(k)

    return ret

def generate_move_ops(output_paths, file_groups):
    for output_path, basenames in output_paths.items():
        seq = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' #TODO make this a generator to handle infinite conflicts
        seq_counter = 0

        # sort the basenames to preserve sequencing of files captured in the same second
        for basename in sorted(basenames):
            for ext in file_groups[basename]:
                from_path = basename + ext
                to_path = (output_path + seq[seq_counter]).strip() + ext
                yield (from_path, to_path)
            seq_counter += 1

def setup_argparser():
    parser = ArgumentParser(description='Imports a directory of photos into dated directories with dated filenames.')
    parser.set_defaults(pretend=False)
    parser.add_argument('--input_dir', required=True, help='Directory to read files from (non-recursive)')
    parser.add_argument('--output_dir', required=True, help='Directory to place dated directories and files')
    parser.add_argument('--prefix', default='', required=False, help='Prefix that will be placed onto the name of each file, such as photographer initials')
    parser.add_argument('--default_event', default='', required=False, help='Default event name to place at the end of each dated directory name')
    parser.add_argument('--pretend', dest='pretend', action='store_true', help="Don't actually execute copy commands, just list them out")
    parsed = parser.parse_args()
    return parsed

if __name__ == "__main__":
    args = setup_argparser()
    input_directory = args.input_dir
    output_directory = args.output_dir

    if input_directory == output_directory:
        logging.error('Input directory cannot be the same as the output directory')

    files = os.listdir(input_directory)
    files = ( input_directory + os.sep + f for f in files )
    files = ( f for f in files if os.path.isfile(f) )
    file_groups = group_files(files)

    capture_times = { basename: determine_capture_time(basename, extensions) for basename, extensions in file_groups.items() }
    file_groups = { basename: extensions for basename, extensions in file_groups.items() if capture_times[basename] is not None }
    output_dirs = { basename: determine_output_dir(output_directory, capture_times[basename], args.default_event) for basename in file_groups }

    # need to ensure the new filenames containing the capture time don't conflict
    # within their new output directories
    output_paths = { basename: output_dirs[basename]+os.sep+make_name(args.prefix, capture_times[basename]) for basename in file_groups }
    output_paths = transpose_dict(output_paths) # transpose so we can generate the move operations as a reduce

    for d in set(output_dirs.values()):
        make_output_dir(d, pretend=args.pretend)

    for from_path, to_path in generate_move_ops(output_paths, file_groups):
        copy_file(from_path, to_path, pretend=args.pretend)
