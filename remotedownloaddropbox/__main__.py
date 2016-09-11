#!/usr/bin/env python3

import configparser
import os

import dropbox

def main():
    config_dir = os.path.join(
        os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config'),
        'remotedownload-dropbox')
    config_filename = os.path.join(config_dir, 'config.ini')

    config = configparser.ConfigParser()
    if len(config.read(config_filename)) == 0:
        raise Exception("Configuration file couldn't be read: %s" % config_filename)

    dbx = dropbox.Dropbox(config['default']['access token'])

    upload_cursor = dropbox.files.UploadSessionCursor(dbx.files_upload_session_start(b'').session_id, 0)
    def add_bytes(bytes_to_upload):
        dbx.files_upload_session_append_v2(bytes_to_upload, upload_cursor)
        upload_cursor.offset += len(bytes_to_upload)
    add_bytes('hello'.encode('utf-8'))
    add_bytes(' once more'.encode('utf-8'))
    dbx.files_upload_session_finish(b'', upload_cursor, dropbox.files.CommitInfo('/hi.txt', dropbox.files.WriteMode.add, autorename=True))
