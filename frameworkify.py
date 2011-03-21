#!/usr/bin/env python -S
# -*- coding: utf-8 -*-
r"""
    frameworkify
    ~~~~~~~~~~~~

    A small command line tool that can rewrite the paths to dynamic
    loaded libraries in .dylib files so that they reference other
    paths.  By default it will rewrite the path so that it points to
    the bundle's Frameworks folder.  This can be paired with a CMake
    post build action to make proper bundles without having to
    recompile a bunch of dylibs to reference the framework.

    Usage::

        $ frameworkify.py MyApplication.app/Contents/MacOS/MyApplication \
        > /path/to/mylib.dylib

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import os
import sys
from optparse import OptionParser


def find_bundle(executable):
    executable = os.path.abspath(executable)
    if not os.path.isfile(executable):
        raise RuntimeError('Executable does not exist')
    folder, exe_name = os.path.split(executable)
    content_path, folder = os.path.split(folder)
    if folder != 'MacOS':
        raise RuntimeError('Executable not located inside a bundle')
    return content_path


def find_baked_dylibs(executable):
    from subprocess import Popen, PIPE
    c = Popen(['otool', '-L', executable], stdout=PIPE)
    lines = c.communicate()[0].splitlines()
    return [x.strip().split(' (')[0] for x in lines[1:]]


def find_matching_dylib(dylibs, basename):
    lbasename = basename.lower()
    for dylib in dylibs:
        if os.path.basename(dylib).lower() == lbasename:
            return dylib


def rewrite_path(executable, old, new):
    from subprocess import Popen
    Popen(['install_name_tool', '-change', old, new, executable]).wait()


def copy_to_framework(bundle_path, filename, target_name):
    from shutil import copy2
    framework_path = os.path.join(bundle_path, 'Frameworks')
    if not os.path.isdir(framework_path):
        os.mkdir(framework_path)
    copy2(filename, os.path.join(framework_path, target_name))


def perform_rewrite_operation(rewrites, executable, bundle_path, copy=True):
    for old_path, new_path, dylib_path in rewrites:
        rewrite_path(executable, old_path, new_path)
        if copy:
            copy_to_framework(bundle_path, dylib_path,
                              os.path.basename(new_path))


def frameworkify(executable, dylibs, nocopy, path):
    bundle = find_bundle(executable)
    baked_dylibs = find_baked_dylibs(executable)

    def _make_new_path(dylib_name):
        if path:
            return os.path.join(path, dylib_name)
        return '@executable_path/../Frameworks/' + dylib_name

    rewrites = []
    for dylib in dylibs:
        dylib_name = os.path.basename(dylib)
        dylib_path_match = find_matching_dylib(baked_dylibs, dylib_name)
        if dylib_path_match is None:
            raise Exception('dylib "%s" is not referenced by "%s"' % (
                dylib_name,
                executable
            ))
        rewrites.append((dylib_path_match, _make_new_path(dylib_name), dylib))

    perform_rewrite_operation(rewrites, executable, bundle, not nocopy)


def main():
    parser = OptionParser()
    parser.add_option('-p', '--path', dest='path', metavar='PATH',
                      help='alternative path to dylib')
    parser.add_option('-C', '--nocopy', dest='nocopy', action='store_true',
                      help='don\'t copy dylib to framework folder')

    opts, args = parser.parse_args()
    if len(args) < 2:
        parser.error('Not enough arguments: executable and a list of dylibs')

    if opts.path and not opts.nocopy:
        parser.error('Path combined with copy operation is not supported')

    try:
        frameworkify(args[0], args[1:], opts.nocopy, opts.path)
    except Exception, e:
        parser.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
