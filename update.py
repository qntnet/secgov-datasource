import gzip
import json
import sys
import zipfile

from config import *
from http_api import load_file
from lock import exclusive_lock, shared_lock
from parser import parse_form
from ppexecutor import ProcessPoolExecutor
from secgov_api import load_report_list, get_xbrl_link

logger = logging.getLogger(__name__)


def update(limit=sys.maxsize, process_count=1):
    os.makedirs(PARSED_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    ppe = ProcessPoolExecutor(process_count) # prevents leaks

    for fd in load_report_list():
        if limit == 0:
            break

        with shared_lock():
            try:
                with zipfile.ZipFile(os.path.join(PARSED_DIR, fd['cik'], 'content.zip'), 'r') as z:
                    if (fd['file'] + '.json') in z.namelist():
                        continue
            except FileNotFoundError:
                pass

        ignored = []
        try:
            with shared_lock():
                with gzip.open(os.path.join(PARSED_DIR, fd['cik'], 'ignored.txt.gz'), 'rt') as f:
                    ignored = f.read().split('\n')
                    ignored = [i.split(':', 1)[1] for i in ignored[:-1]]
        except FileNotFoundError:
            pass

        if fd['file'] in ignored:
            continue

        limit -= 1

        ppe.exec(parse_raw_one, [fd])

    ppe.join()


def parse_raw_one(fd):
    print("process:", fd)
    try:
        raw_path = os.path.join(RAW_DIR, fd['cik'] + '.' + fd['file'] + '.gz')

        os.makedirs(os.path.join(PARSED_DIR, fd['cik']), exist_ok=True)

        url = get_xbrl_link(fd)
        if url is None:
            with exclusive_lock():
                with gzip.open(os.path.join(PARSED_DIR, fd['cik'], 'ignored.txt.gz'), 'at') as f:
                    f.write("no_url:" + fd['file'] + '\n')
            return

        fd['url'] = url

        os.makedirs(os.path.dirname(raw_path), exist_ok=True)

        load_file(url, raw_path)

        with gzip.open(raw_path, 'rb') as f:
            content = f.read()

        content = parse_form(content)

        if content is None or len(content['facts']) < 1:
            with exclusive_lock():
                with gzip.open(os.path.join(PARSED_DIR, fd['cik'], 'ignored.txt.gz'), 'at') as f:
                    f.write("no_data:" +fd['file'] + '\n')
            return

        content['id'] = fd['file']
        content['type'] = fd['type']
        content['cik'] = fd['cik']
        content['date'] = fd['date']
        content['name'] = fd['name']
        content['url'] = url

        with exclusive_lock():
            with zipfile.ZipFile(os.path.join(PARSED_DIR, fd['cik'], 'content.zip'), 'a', compresslevel=9, compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr(fd['file'] + '.json', json.dumps(content, indent=1))
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)


def update_indexes():
    os.makedirs(PARSED_DIR, exist_ok=True)

    global_index = []
    for i in os.listdir(PARSED_DIR):
        if os.path.isfile(os.path.join(PARSED_DIR, i)):
            continue
        logger.info("reindex: " + i)
        local_index = []
        try:
            with shared_lock():
                with zipfile.ZipFile(os.path.join(PARSED_DIR, i,  'content.zip'), 'r') as z:
                    for j in z.namelist():
                        content = z.read(j).decode()
                        content = json.loads(content)
                        local_index.append({
                            'id': content['id'],
                            'name': content['name'],
                            'date': content['date'],
                            'type': content['type'],
                            'facts': len(content['facts'])
                        })
        except FileNotFoundError:
            continue
        except:
            logger.exception('wtf')
            with exclusive_lock():
                os.remove(os.path.join(PARSED_DIR, i,  'content.zip'))
                continue

        local_index.sort(key=lambda i: (i['date'], i['id']))

        if len(local_index) == 0:
            continue
        with exclusive_lock():
            with gzip.open(os.path.join(PARSED_DIR, i, 'index.json.gz'), 'wt') as f:
                f.write(json.dumps(local_index, indent=1))

        global_index.append({
            'cik': i,
            'name': local_index[-1]['name'],
            'reports': len(local_index),
            'last_date': local_index[-1]['date']
        })

    global_index.sort(key=lambda i: i['cik'])
    with exclusive_lock():
        with gzip.open(os.path.join(PARSED_DIR, 'index.json.gz'), 'wt') as f:
            f.write(json.dumps(global_index, indent=1))


if __name__ == '__main__':
    update_indexes()
    update()
    update_indexes()
