#!/usr/bin/env python3

import configparser
import os
import sys
import tempfile
import threading
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

    class DualProgressReporter:

        def __init__(self):
            self.start_time = time.time()
            self._doing = 0
            self._download_progress = 0
            self._download_kbytesps = 0
            self._upload_progress = 0
            self._upload_kbytesps = 0
            self._lock = threading.Lock()
            print('\n' * 2, end='')

        def download_progress(self, done, doing):
            self._doing = doing
            (self._download_progress, self._download_kbytesps) = self.progress(done, doing)
            self.print_both_bars()

        def upload_progress(self, done):
            (self._upload_progress, self._upload_kbytesps) = self.progress(done, self._doing)
            self.print_both_bars()

        def progress(self, done, doing):
            progress = float(done) / doing if doing != 0 else 1
            kbytesps = (done / (time.time() - self.start_time)) / 1024
            return (progress, kbytesps)

        def print_both_bars(self):
            if not self._lock.acquire(blocking=False): return # Don't bother waiting if busy.
            print('\033[F' * 2, end='')
            self.print_bar("Download", self._download_progress, self._download_kbytesps)
            self.print_bar("Upload", self._upload_progress, self._upload_kbytesps)
            self._lock.release()

        def print_bar(self, prefix, progress, kbytesps):
            bar_width = 50
            bars = int(progress * bar_width)
            spaces = bar_width - bars

            print(\
                ('%-9s' % prefix) + \
                '[' + ('#' * bars) + (' ' * spaces) + ']' + \
                (' %d kB/s' % kbytesps))

    for url in downloader.urls:
        print("Starting: %s" % url)
        upload = DropboxFileUpload()
        with tempfile.NamedTemporaryFile('wb') as write_file:
            with open(write_file.name, 'rb') as read_file:
                progress_reporter = DualProgressReporter()
                filename = None
                completed_download = False
                def download():
                    nonlocal filename, completed_download
                    filename = downloader.get(url,
                        AutoFlushingFileWrapper(write_file),
                        progress_reporter=progress_reporter.download_progress)
                    completed_download = True
                download_thread = threading.Thread(target=download)
                download_thread.start()
                max_upload_chunk_size = 16 * (2 ** 20)
                total_uploaded = 0
                while True:
                    upload_chunk = read_file.read(max_upload_chunk_size)
                    upload_chunk_length = len(upload_chunk)
                    if upload_chunk_length == 0:
                        if completed_download:
                            break
                        else:
                            time.sleep(1) # wait for more data
                            continue
                    upload.write(upload_chunk)
                    total_uploaded += upload_chunk_length
                    progress_reporter.upload_progress(total_uploaded)
                upload.commit(filename)
        print("Finished saving: %s" % filename)
