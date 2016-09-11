#!/usr/bin/env python3

import configparser
import os
import sys

import dropbox

import remotedownload

def main():
    config_dir = os.path.join(
        os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config'),
        'remotedownload-dropbox')
    config_filename = os.path.join(config_dir, 'config.ini')

    config = configparser.ConfigParser()
    if len(config.read(config_filename)) == 0:
        raise Exception("Configuration file couldn't be read: %s" % config_filename)

    downloader = remotedownload.Downloader(sys.stdin.buffer.read())

    dbx = dropbox.Dropbox(config['default']['access token'])

    class DropboxFileUpload:
        """A file-like object for uploading to a Dropbox upload session"""

        def __init__(self):
            self._cursor = dropbox.files.UploadSessionCursor(dbx.files_upload_session_start(b'').session_id, 0)

        def write(self, data):
            # The Dropbox API will happily take a string but we need to know the length of its byte representation to advance the cursor so just convert it ourselves:
            data_bytes = data.encode('utf-8') if type(data) is str else data
            dbx.files_upload_session_append_v2(data_bytes, self._cursor)
            self._cursor.offset += len(data_bytes)

        def commit(self, filename):
            dbx.files_upload_session_finish(b'', self._cursor,
                dropbox.files.CommitInfo('/%s' % filename, dropbox.files.WriteMode.add, autorename=True))

    for url in downloader.urls:
        upload = DropboxFileUpload()
        filename = downloader.get(url, upload, chunk_size=2 ** 20)
        upload.commit(filename)
