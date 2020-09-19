import os
import time
import subprocess
import shlex
import logging
from itertools import filterfalse
from pathlib import Path
import json
import time
import sys

TOKEN=sys.argv[1]
CHANNEL=sys.argv[2]

log = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S')
SSTV_RX_DIR = "/home/pi/qsstv/rx_sstv"
SUPPORTED_EXTENSIONS = ['.png']
UPLOADED_SENTINAL_TEMPLATE = "{}_uploaded"
def mark_uploaded(file_name):
    marker = UPLOADED_SENTINAL_TEMPLATE.format(file_name)
    marker = os.path.join(SSTV_RX_DIR, marker)
    log.info(f"Marking file as uploaded: {marker}")
    Path(marker).touch()

def new_pics():
    log.debug("Getting list of new pictures")
    dir_contents = os.listdir(SSTV_RX_DIR)
    candidates = []
    for c in dir_contents:
        _, ext = os.path.splitext(c)
        print(c)
        if ext in SUPPORTED_EXTENSIONS:
            log.debug(f"Found candidate {c}")
            candidates.append(c)
        log.debug("Checking if candidates are already uploaded")
    candidates[:] = filterfalse(lambda x: UPLOADED_SENTINAL_TEMPLATE.format(x) in dir_contents, candidates)
    log.debug("After filtering, candidate upload list is: {}".format(candidates))
    return candidates

def append_metadata(pic_list):
    for p in pic_list:
        f = Path(os.path.join(SSTV_RX_DIR, p +".meta"))
        if f.exists():
            metadata = f.read_text()
            image_file = os.path.join(SSTV_RX_DIR, p)
            im = "convert {} -background YellowGreen label:'{}' -gravity Center -append {}".format(image_file, str(metadata), image_file)
            subprocess.run(shlex.split(im), capture_output=False)

def upload(files, to_thread=False):
    if to_thread:
        curl_cli = 'curl -X POST --data \'{{"channel":"{}","text":"New batch of images"}}\' -H \'Content-type: application/json\'  -H "Authorization: Bearer {}" https://slack.com/api/chat.postMessage'.format(CHANNEL, TOKEN)
        log.debug(curl_cli)
        result = subprocess.run(shlex.split(curl_cli), capture_output=True)
        res = json.loads(result.stdout.decode('utf-8'))
        log.debug(res)
        if result.returncode != 0 or res['ok'] == False:
            log.error("Unable to make new thread.  Will retry transfer later")
            return
        thread_ts = res['ts']
    for f in files:
        f = os.path.join(SSTV_RX_DIR, f)
        if to_thread:
            cmd = f'curl -F file=@{f} -F thread_ts={thread_ts} -F channels={CHANNEL} -H "Authorization: Bearer {TOKEN}" https://slack.com/api/files.upload'
        else:
            cmd = f'curl -F file=@{f} -F channels={CHANNEL} -H "Authorization: Bearer {TOKEN}" https://slack.com/api/files.upload'

        log.debug(f"Executing: {cmd}")
        args = shlex.split(cmd)
        result = subprocess.run(args, capture_output=True)
        if result.returncode != 0:
            log.error("Unable to upload image")
        mark_uploaded(f)

def poll(interval=60, upload_threshold=1, timeout_upload_period_s = 3600.0):
    last_upload = time.monotonic()
    while True:
        time.sleep(interval)
        pics_to_upload = new_pics()
        append_metadata(pics_to_upload)
        if len(pics_to_upload) == 0:
            log.debug("No images have been received")
        elif len(pics_to_upload) >= upload_threshold or ((time.monotonic() - last_upload) > timeout_upload_period_s):
            upload(pics_to_upload)
            last_upload = time.monotonic()
        else:
            log.debug("Not uploading, even though {} pics are ready.".format(len(pics_to_upload)))

if __name__ == '__main__':
    poll()
