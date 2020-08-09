import gzip
import json
import os
import zipfile

from flask import Flask, jsonify, safe_join, send_file, request
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from config import DEBUG, FILE_NAME_DELIMITER, PARSED_DIR
from lock import shared_lock

app = Flask("blsgov-datasource")
app.wsgi_app = ProxyFix(app.wsgi_app)


@app.route('/api/files/<path:path>')
@app.route('/api/files/')
def get_files(path=''):
    with shared_lock():
        path = safe_join(PARSED_DIR, path) if len(path) > 0 else PARSED_DIR
        if not os.path.exists(path):
            raise NotFound()
        if os.path.isdir(path):
            lst = os.listdir(path)
            lst = [{"name": i, "type": 'dir' if os.path.isdir(os.path.join(path, i)) else 'file'} for i in lst]
            return jsonify(lst)
        else:
            return send_file(path, as_attachment=True)


@app.route('/api/company/')
@app.route('/api/company/<id>')
def get_company(id = None):
    with shared_lock():
        with gzip.open(os.path.join(PARSED_DIR, 'index.json.gz'), 'rt') as f:
            companies = f.read()
    companies = json.loads(companies)
    if id is not None:
        company = next((i for i in companies if i['cik'] == id), None)
        if company is None:
            raise NotFound()
        else:
            return jsonify(company)
    else:
        return jsonify(companies)


@app.route('/api/company/<id>/report')
def get_report_list(id):
    try:
        with shared_lock():
            with gzip.open(os.path.join(PARSED_DIR, id, 'index.json.gz'), 'rt') as f:
                result = f.read()
    except FileNotFoundError:
        raise NotFound()
    result = json.loads(result)
    return jsonify(result)


@app.route('/api/company/<cid>/report/<rid>')
def get_report(cid, rid):
    try:
        with shared_lock():
            with zipfile.ZipFile(os.path.join(PARSED_DIR, cid, 'content.zip'), 'r') as z:
                result = z.read(rid + '.json').decode()
    except FileNotFoundError:
        raise NotFound()
    except KeyError:
        raise NotFound()
    result = json.loads(result)
    return jsonify(result)


app.debug = DEBUG

if __name__ == '__main__':
    app.run(host='0.0.0.0')
