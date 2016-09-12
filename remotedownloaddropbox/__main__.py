#!/usr/bin/env python3

import configparser
import os
import sys
import tempfile
import time

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
            self._cursor = None

        def write(self, data):
            # The Dropbox API will happily take a string but we need to know the length of its byte representation to advance the cursor so just convert it ourselves:
            data_bytes = data.encode('utf-8') if type(data) is str else data
            if self._cursor is None:
                self._cursor = dropbox.files.UploadSessionCursor(dbx.files_upload_session_start(data_bytes).session_id, 0)
            else:
                dbx.files_upload_session_append_v2(data_bytes, self._cursor)
            self._cursor.offset += len(data_bytes)

        def commit(self, filename):
            dbx.files_upload_session_finish(b'', self._cursor,
                dropbox.files.CommitInfo('/%s' % filename, dropbox.files.WriteMode.add, autorename=True))

    class AutoFlushingFileWrapper:
        def __init__(self, file):
            self._file = file
        def write(self, data):
            self._file.write(data)
            self._file.flush()

    for url in downloader.urls:
        print("Starting: %s" % url)
        upload = DropboxFileUpload()
        with tempfile.NamedTemporaryFile('wb') as write_file:
            with open(write_file.name, 'rb') as read_file:
                completed_download = False
                filename = downloader.get(url,
                    AutoFlushingFileWrapper(write_file),
                    progress_reporter=remotedownload.ProgressReporter())
                completed_download = True
                max_upload_chunk_size = 16 * (2 ** 20)
                while True:
                    upload_chunk = read_file.read(max_upload_chunk_size)
                    if len(upload_chunk) == 0:
                        if completed_download:
                            break
                        else:
                            time.sleep(1) # wait for more data
                            continue
                    upload.write(upload_chunk)
                upload.commit(filename)
        print("Finished saving: %s" % filename)
